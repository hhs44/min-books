"""Pipeline 启动 / 状态 / 取消 / SSE 端点(v4 §Phase D Task 10)。

- POST /internal/pipeline/write/next  → 创建 run + 入调度 queue
- GET  /internal/pipeline/status/{run_id}  → 返 status / checkpoints / error
- POST /internal/pipeline/cancel/{run_id}  → 发 NATS 取消事件
- GET  /internal/pipeline/stream/{run_id}  → SSE 流
"""
import asyncio
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import state
from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


class WriteNextRequest(BaseModel):
    book_id: UUID
    chapter_number: int
    current_focus: str = ""
    book_settings: dict[str, Any] = {}
    initial_inputs: dict[str, Any] = {}


@router.post("/write/next")
async def write_next(body: WriteNextRequest):
    """启动 'write/next' Pipeline Run(从 gateway 调)。"""
    # 1. 选 DAG(暂固定 chapter_writing_v2)
    dag_id = "chapter_writing_v2"
    if state.dag_loader and not state.dag_loader.get(dag_id):
        # 兜底:拿第一个可用的 DAG
        ids = state.dag_loader.list_ids()
        if not ids:
            raise HTTPException(status_code=503, detail="No DAG definitions loaded")
        dag_id = ids[0]

    # 2. 创建 run 记录
    run_id = uuid4()
    initial = {
        "book_settings": body.book_settings,
        "current_focus": body.current_focus,
        "chapter_number": body.chapter_number,
        **body.initial_inputs,
    }
    dag_definition_snapshot = {
        "id": dag_id,
        "initial_inputs": initial,
    }
    try:
        async with acquire() as conn:
            await conn.execute(
                """INSERT INTO orchestrator.pipeline_runs
                   (id, pipeline_id, book_id, status, dag_definition, checkpoints)
                   VALUES ($1::uuid, $2, $3::uuid, 'pending', $4::jsonb, '{}'::jsonb)""",
                run_id, dag_id, body.book_id,
                json.dumps(dag_definition_snapshot),
            )
    except Exception as e:
        logger.exception(f"Failed to create pipeline_run: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create run: {e}")

    # 3. 入调度队列
    if state.scheduler_queue is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    await state.scheduler_queue.put({
        "id": str(run_id),
        "pipeline_id": dag_id,
        "book_id": str(body.book_id),
        "checkpoints": {},
        "initial_inputs": initial,
    })
    logger.info(f"Pipeline run {run_id} created (book={body.book_id}, dag={dag_id})")

    return {"pipeline_run_id": str(run_id), "status": "pending"}


@router.get("/status/{run_id}")
async def get_status(run_id: UUID):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, pipeline_id, book_id, status, checkpoints, error,
                      started_at, completed_at
               FROM orchestrator.pipeline_runs WHERE id = $1::uuid""",
            run_id,
        )
    if not row:
        raise HTTPException(404, "Run not found")
    return {
        "pipeline_run_id": str(row["id"]),
        "pipeline_id": row["pipeline_id"],
        "book_id": str(row["book_id"]),
        "status": row["status"],
        "checkpoints": _normalize_jsonb(row["checkpoints"]),
        "error": _normalize_jsonb(row["error"]),
        "started_at": str(row["started_at"]) if row["started_at"] else None,
        "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
    }


@router.post("/cancel/{run_id}")
async def cancel(run_id: UUID):
    """用户主动取消:发 NATS 事件 + 直接调 cancel_run() 兜底。"""
    from ..saga.cancellation import cancel_run  # 避免循环 import

    # 1. 直接触发 cancel(更新 DB + 通知 active executor)
    await cancel_run(str(run_id), reason="user_requested")

    # 2. 同时发 NATS 事件(其他实例可收到广播)
    if state.nats:
        try:
            await state.nats.publish_event(
                f"minbook.pipeline.{run_id}.cancel",
                data={"pipeline_run_id": str(run_id), "reason": "user_requested"},
            )
        except Exception as e:
            logger.debug(f"Failed to publish cancel event: {e}")

    return {"status": "cancelling", "pipeline_run_id": str(run_id)}


@router.get("/stream/{run_id}")
async def stream_run(run_id: UUID):
    """SSE 流式输出 run 进度(gateway 调)。"""

    async def event_gen():
        last_checkpoints: dict = {}
        last_status: str | None = None
        # 60s × 200 = 最长 200 分钟(可配)
        for _ in range(7200):
            try:
                async with acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT status, checkpoints FROM orchestrator.pipeline_runs WHERE id = $1::uuid",
                        run_id,
                    )
            except Exception as e:
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
                break

            if not row:
                yield f"data: {json.dumps({'event': 'not_found'})}\n\n"
                break

            current = _normalize_jsonb(row["checkpoints"]) or {}
            status = row["status"]

            # 推送新增的 checkpoint
            for node_id, ckpt in current.items():
                if node_id not in last_checkpoints:
                    yield f"data: {json.dumps({'event': 'node_completed', 'node_id': node_id, 'output': ckpt.get('output', {})})}\n\n"
            last_checkpoints = current

            # 状态变化推送
            if status != last_status:
                yield f"data: {json.dumps({'event': 'status', 'status': status})}\n\n"
                last_status = status

            if status in ("completed", "failed", "cancelled", "dropped"):
                yield f"data: {json.dumps({'event': 'done', 'status': status})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _normalize_jsonb(value) -> Any:
    """asyncpg 默认返 str(jsonb),统一 loads。"""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value
