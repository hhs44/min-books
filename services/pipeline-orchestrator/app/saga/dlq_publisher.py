"""DLQ 发布(详见 v4 §Phase B Task 8 + v2 spec §11 §7)。"""
import json
import logging
from datetime import datetime
from uuid import UUID

from minbook_common.nats_client import MinBookNATS

from ..db import acquire

logger = logging.getLogger(__name__)


class DLQPublisher:
    """把 pipeline / node 失败信息通过 NATS JetStream 发到 DLQ。"""

    def __init__(self, nats: MinBookNATS):
        self.nats = nats

    async def publish_pipeline_failed(
        self,
        pipeline_run_id: UUID | str,
        book_id: UUID | str,
        failed_node_id: str,
        error: Exception,
        checkpoints: dict[str, dict] | None = None,
    ):
        """发 DLQ 事件(详见 §11 §7.1)。"""
        llm_summary = await self._summarize_llm_calls(book_id, pipeline_run_id)

        payload = {
            "pipeline_run_id": str(pipeline_run_id),
            "book_id": str(book_id),
            "chapter_number": 0,  # TODO:从 run 取
            "failed_node_id": failed_node_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_stack": "",  # 不放 stack 到 NATS(太大)
            "checkpoints_at_failure": {
                k: {"status": v.get("status")} for k, v in (checkpoints or {}).items()
            },
            "llm_calls_summary": llm_summary,
            "occurred_at": datetime.utcnow().isoformat(),
        }
        try:
            await self.nats.publish_event("minbook.dlq.pipeline.failed", data=payload)
            logger.info(f"Pipeline {pipeline_run_id} sent to DLQ (failed_node={failed_node_id})")
        except Exception as e:
            logger.exception(f"Failed to publish DLQ event for run {pipeline_run_id}: {e}")

    async def publish_node_failed(
        self,
        pipeline_run_id: UUID | str,
        node_id: str,
        error: Exception,
        retry_count: int,
    ):
        payload = {
            "pipeline_run_id": str(pipeline_run_id),
            "node_id": node_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "retry_count": retry_count,
            "occurred_at": datetime.utcnow().isoformat(),
        }
        try:
            await self.nats.publish_event("minbook.dlq.node.failed", data=payload)
        except Exception as e:
            logger.exception(f"Failed to publish node DLQ event: {e}")

    async def _summarize_llm_calls(self, book_id, pipeline_run_id) -> dict:
        """从 llm.llm_calls 汇总。"""
        try:
            async with acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT COUNT(*) AS call_count,
                              COALESCE(SUM(cost_estimate), 0) AS total_cost,
                              COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                              COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                       FROM llm.llm_calls
                       WHERE book_id = $1 AND pipeline_run_id = $2""",
                    str(book_id), str(pipeline_run_id),
                )
            return {
                "total_cost_usd": float(row["total_cost"]) if row else 0.0,
                "total_tokens": (row["prompt_tokens"] + row["completion_tokens"]) if row else 0,
                "call_count": row["call_count"] if row else 0,
            }
        except Exception as e:
            logger.debug(f"Failed to summarize LLM calls: {e}")
            return {"total_cost_usd": 0.0, "total_tokens": 0, "call_count": 0}
