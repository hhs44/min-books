"""Stale Run 扫描 + 恢复(详见 v2 §11 §8 + v4 §Phase D Task 14)。

5 分钟无更新的 running run → 视为 stale,从最后成功 node 重跑。
"""
import asyncio
import logging

from ..db import acquire

logger = logging.getLogger(__name__)


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
            # orchestrator.pipeline_runs 表用 started_at / completed_at, 没有 updated_at
            # 用 COALESCE(started_at, ...) 兜底(更精确的应加 trigger / 显式 updated_at 字段)
            stale_runs = await conn.fetch(
                f"""SELECT id, pipeline_id, book_id, dag_definition, checkpoints
                    FROM orchestrator.pipeline_runs
                    WHERE status IN ('running', 'cancelling')
                      AND COALESCE(started_at, NOW()) < NOW() - INTERVAL '{self.threshold} seconds'"""
            )

        for run in stale_runs:
            logger.warning(f"Stale run detected: {run['id']} (last update > {self.threshold}s ago)")
            async with acquire() as conn:
                await conn.execute(
                    """UPDATE orchestrator.pipeline_runs
                       SET status = 'failed', completed_at = NOW(),
                           error = '{"error_type": "stale_recovery"}'::jsonb
                       WHERE id = $1""",
                    run["id"],
                )
            # 注:实际应重新入调度队列(Phase E 集成时实现)
