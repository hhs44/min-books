"""DLQ 同步:NATS stream → orchestrator.dlq 表(详见 v2 §11 §7.5 + v4 §Phase D Task 15)。"""
import asyncio
import json
import logging
from datetime import datetime

from minbook_common.nats_client import MinBookNATS

from ..db import acquire

logger = logging.getLogger(__name__)


class DLQSyncer:
    def __init__(self, sync_interval: int = 60):
        self.sync_interval = sync_interval
        self._nats: MinBookNATS | None = None

    async def run_forever(self):
        # 实际 NATS subscribe 在 main.py lifespan 中做;这里仅 keep-alive
        while True:
            await asyncio.sleep(3600)

    async def _handle_pipeline_failed(self, event: dict):
        data = event.get("data", {})
        try:
            occurred_at_raw = data.get("occurred_at")
            if occurred_at_raw:
                try:
                    occurred_at = datetime.fromisoformat(occurred_at_raw)
                except Exception:
                    occurred_at = datetime.utcnow()
            else:
                occurred_at = datetime.utcnow()

            async with acquire() as conn:
                await conn.execute(
                    """INSERT INTO orchestrator.dlq
                       (pipeline_run_id, book_id, chapter_number, failed_node_id,
                        error_type, error_message, error_stack, checkpoints_at_failure,
                        llm_calls_summary, occurred_at, status)
                       VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, 'pending')
                       ON CONFLICT (pipeline_run_id) DO NOTHING""",
                    data.get("pipeline_run_id"),
                    data.get("book_id"),
                    data.get("chapter_number", 0),
                    data.get("failed_node_id"),
                    data.get("error_type", "unknown"),
                    data.get("error_message", ""),
                    data.get("error_stack", ""),
                    json.dumps(data.get("checkpoints_at_failure", {})),
                    json.dumps(data.get("llm_calls_summary", {})),
                    occurred_at,
                )
            logger.info(f"Synced DLQ entry: {data.get('pipeline_run_id')}")
        except Exception as e:
            logger.exception(f"DLQ sync error: {e}")

    async def _handle_node_failed(self, event: dict):
        # 节点失败不入 DLQ,只入 pg.log(简化版略)
        pass
