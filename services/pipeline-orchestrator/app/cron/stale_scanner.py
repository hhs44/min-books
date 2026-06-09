"""Stale Run 扫描 + 恢复(详见 v2 §11 §8 + v4 §Phase D Task 14)。

5 分钟无更新的 running run → 视为 stale:
  1. 标 status='failed', error=stale_recovery
  2. 创建新 run(继承 checkpoints),入调度队列(从最后成功节点重跑)
  3. 发 NATS 事件 minbook.pipeline.resumed
"""
import asyncio
import json
import logging

from ..db import acquire

logger = logging.getLogger(__name__)


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


class StaleScanner:
    def __init__(self, stale_threshold_seconds: int = 300):
        self.threshold = stale_threshold_seconds

    async def run_forever(self, scan_interval: int = 60):
        while True:
            try:
                await self._scan_once()
            except Exception as e:
                logger.exception(f"Stale scan error: {e}")
            await asyncio.sleep(scan_interval)

    async def _scan_once(self):
        async with acquire() as conn:
            # orchestrator.pipeline_runs 表用 started_at,没有 updated_at
            # 用 COALESCE(started_at, NOW()) 兜底
            stale_runs = await conn.fetch(
                f"""SELECT id, pipeline_id, book_id, dag_definition, checkpoints
                    FROM orchestrator.pipeline_runs
                    WHERE status IN ('running', 'cancelling')
                      AND COALESCE(started_at, NOW()) < NOW() - INTERVAL '{self.threshold} seconds'"""
            )

        for run in stale_runs:
            logger.warning(
                f"Stale run detected: {run['id']} (last update > {self.threshold}s ago)"
            )
            await self._recover_run(run)

    async def _recover_run(self, run: dict) -> None:
        """标记 stale + 入队恢复。"""
        checkpoints = _normalize(run["checkpoints"]) or {}
        dag_def = _normalize(run["dag_definition"]) or {}
        initial_inputs = dag_def.get("initial_inputs") or {}
        last_completed = list(checkpoints.keys())[-1] if checkpoints else None

        # 延迟 import 避免循环
        from uuid import uuid4
        from .. import state

        # 1. 标原 run 为 failed(stale_recovery)
        try:
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET status = 'failed', completed_at = NOW(),
                           error = '{"error_type": "stale_recovery"}'::jsonb
                       WHERE id = $1::uuid""",
                    run["id"],
                )
        except Exception as e:
            logger.exception(f"Stale: failed to mark run {run['id']} as failed: {e}")
            return

        # 2. 创建新 run(继承 checkpoints, resume from last_completed)
        new_run_id = uuid4()
        try:
            async with acquire() as conn:
                await conn.execute(
                    """INSERT INTO orchestrator.pipeline_runs
                       (id, pipeline_id, book_id, status, dag_definition, checkpoints)
                       VALUES ($1::uuid, $2, $3::uuid, 'pending', $4::jsonb, $5::jsonb)""",
                    new_run_id, run["pipeline_id"], run["book_id"],
                    json.dumps({
                        "id": run["pipeline_id"],
                        "initial_inputs": initial_inputs,
                        "resumed_from_node": last_completed,
                        "resumed_from_stale_run_id": str(run["id"]),
                    }),
                    json.dumps(checkpoints),
                )
        except Exception as e:
            logger.exception(f"Stale: failed to create resumed run: {e}")
            return

        # 3. 入队
        if state.scheduler_queue is not None:
            await state.scheduler_queue.put({
                "id": str(new_run_id),
                "pipeline_id": run["pipeline_id"],
                "book_id": str(run["book_id"]),
                "checkpoints": checkpoints,
                "initial_inputs": initial_inputs,
                "resumed_from_stale": True,
            })
            logger.info(
                f"Stale recovery: new run {new_run_id} enqueued (resumed_from={last_completed})"
            )
        else:
            logger.warning("Stale recovery: scheduler_queue not initialized; skipping enqueue")

        # 4. 发 NATS 事件
        if state.nats is not None:
            try:
                await state.nats.publish_event(
                    "minbook.pipeline.resumed",
                    data={
                        "pipeline_run_id": str(new_run_id),
                        "original_run_id": str(run["id"]),
                        "resumed_from_node": last_completed,
                        "stale_reason": "stale_recovery",
                    },
                )
            except Exception as e:
                logger.debug(f"Stale: failed to publish resumed event: {e}")
