"""DLQ 管理端点(v4 §Phase D Task 13)。

- GET    /internal/dlq?status=&limit=        → 列表
- GET    /internal/dlq/stats                 → 汇总
- GET    /internal/dlq/{run_id}             → 详情
- POST   /internal/dlq/{run_id}/retry       → 创建新 run,从最后成功节点重跑
- DELETE /internal/dlq/{run_id}             → 标 'dropped'
"""
import json
import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query

from .. import state
from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize(value):
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


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row)
    for k in ("checkpoints_at_failure", "llm_calls_summary"):
        if k in d:
            d[k] = _normalize(d[k])
    for k in ("occurred_at",):
        if d.get(k) is not None:
            d[k] = str(d[k])
    # UUID → str(避免 JSON 序列化问题)
    for k, v in list(d.items()):
        if hasattr(v, "hex") and not isinstance(v, (str, int, float, bool)):
            d[k] = str(v)
    return d


@router.get("")
async def list_dlq(
    status: Optional[str] = Query(None, description="pending | reviewed | retried | dropped"),
    limit: int = Query(50, le=200),
):
    async with acquire() as conn:
        if status:
            rows = await conn.fetch(
                """SELECT pipeline_run_id, book_id, chapter_number, failed_node_id,
                          error_type, error_message, status, occurred_at
                   FROM orchestrator.dlq WHERE status = $1
                   ORDER BY occurred_at DESC LIMIT $2""",
                status, limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT pipeline_run_id, book_id, chapter_number, failed_node_id,
                          error_type, error_message, status, occurred_at
                   FROM orchestrator.dlq
                   ORDER BY occurred_at DESC LIMIT $1""",
                limit,
            )
    return [_row_to_dict(r) for r in rows]


@router.get("/stats")
async def stats():
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT
                  COUNT(*)::int AS total,
                  COUNT(*) FILTER (WHERE status = 'pending')::int AS pending,
                  COUNT(*) FILTER (WHERE status = 'reviewed')::int AS reviewed,
                  COUNT(*) FILTER (WHERE status = 'retried')::int AS retried,
                  COUNT(*) FILTER (WHERE status = 'dropped')::int AS dropped
               FROM orchestrator.dlq"""
        )
    return dict(row) if row else {"total": 0, "pending": 0, "reviewed": 0, "retried": 0, "dropped": 0}


@router.get("/{run_id}")
async def show(run_id: UUID):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT pipeline_run_id, book_id, chapter_number, failed_node_id,
                      error_type, error_message, error_stack, checkpoints_at_failure,
                      llm_calls_summary, status, occurred_at
               FROM orchestrator.dlq WHERE pipeline_run_id = $1::uuid""",
            run_id,
        )
    if not row:
        raise HTTPException(404, "DLQ entry not found")
    return _row_to_dict(row)


@router.post("/{run_id}/retry")
async def retry_run(run_id: UUID):
    """重新入队(创建新 run, 从失败 node 重跑,详见 §11 §7.4)。"""
    if state.scheduler_queue is None:
        raise HTTPException(503, "Scheduler not initialized")

    async with acquire() as conn:
        dlq_row = await conn.fetchrow(
            "SELECT * FROM orchestrator.dlq WHERE pipeline_run_id = $1::uuid",
            run_id,
        )
        old_run = await conn.fetchrow(
            "SELECT * FROM orchestrator.pipeline_runs WHERE id = $1::uuid",
            run_id,
        )
        if not dlq_row:
            raise HTTPException(404, "Not found in DLQ")
        if not old_run:
            raise HTTPException(404, "Original pipeline run not found")

        # 找最后成功的 node
        checkpoints = _normalize(old_run["checkpoints"]) or {}
        last_completed = list(checkpoints.keys())[-1] if checkpoints else None

        # 拿 original initial_inputs
        dag_def = _normalize(old_run["dag_definition"]) or {}
        initial_inputs = dag_def.get("initial_inputs") or {}

        # 创建新 run(从最后成功节点重跑:把 checkpoints 预填)
        new_run_id = uuid4()
        await conn.execute(
            """INSERT INTO orchestrator.pipeline_runs
               (id, pipeline_id, book_id, status, dag_definition, checkpoints)
               VALUES ($1::uuid, $2, $3::uuid, 'pending', $4::jsonb, $5::jsonb)""",
            new_run_id, old_run["pipeline_id"], old_run["book_id"],
            json.dumps({
                "id": old_run["pipeline_id"],
                "initial_inputs": initial_inputs,
                "resumed_from_node": last_completed,
                "resumed_from_run_id": str(run_id),
            }),
            json.dumps(checkpoints),
        )

        # 标 DLQ 状态:retried
        await conn.execute(
            """UPDATE orchestrator.dlq
               SET status = 'retried'
               WHERE pipeline_run_id = $1::uuid""",
            run_id,
        )

    # 入调度队列
    await state.scheduler_queue.put({
        "id": str(new_run_id),
        "pipeline_id": old_run["pipeline_id"],
        "book_id": str(old_run["book_id"]),
        "checkpoints": checkpoints,
        "initial_inputs": initial_inputs,
        "resumed_from_node": last_completed,
    })
    logger.info(
        f"DLQ retry: new run {new_run_id} created from failed run {run_id} "
        f"(resumed_from_node={last_completed})"
    )
    return {
        "new_pipeline_run_id": str(new_run_id),
        "resumed_from_node": last_completed,
        "resumed_from_run_id": str(run_id),
    }


@router.delete("/{run_id}")
async def drop(run_id: UUID):
    async with acquire() as conn:
        result = await conn.execute(
            """UPDATE orchestrator.dlq
               SET status = 'dropped'
               WHERE pipeline_run_id = $1::uuid""",
            run_id,
        )
    if "UPDATE 0" in (result or ""):
        raise HTTPException(404, "DLQ entry not found")
    return {"status": "dropped", "pipeline_run_id": str(run_id)}
