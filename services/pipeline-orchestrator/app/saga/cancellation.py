"""取消协议(详见 v4 §Phase B Task 9 + v2 spec §11 §4)。"""
import asyncio
import logging
from typing import Any

from ..db import acquire

logger = logging.getLogger(__name__)

# 全局 active runs 表:run_id -> asyncio.Event
# executor 启动时 register,结束时 unregister;cancel_run() 通过 set() 通知
ACTIVE_RUNS: dict[str, asyncio.Event] = {}


def register_active_run(run_id: str, event: asyncio.Event):
    ACTIVE_RUNS[run_id] = event


def unregister_active_run(run_id: str):
    ACTIVE_RUNS.pop(run_id, None)


def get_cancellation_event(run_id: str) -> asyncio.Event | None:
    return ACTIVE_RUNS.get(run_id)


async def cancel_run(run_id: str, reason: str = "user_requested"):
    """由 NATS 事件 / HTTP 触发:标记 DB status='cancelling' + 通知 active executor。

    Args:
        run_id: pipeline run 的 UUID(str 也可,会被 cast)
        reason: 取消原因
    """
    logger.info(f"Cancel requested for run {run_id}: {reason}")

    # 1. 更新 DB (id 是 UUID, 强转)
    try:
        async with acquire() as conn:
            await conn.execute(
                """UPDATE orchestrator.pipeline_runs
                   SET status = 'cancelling'
                   WHERE id = $1::uuid AND status IN ('pending', 'running')""",
                run_id,
            )
    except Exception as e:
        logger.exception(f"Cancel: failed to update DB for run {run_id}: {e}")

    # 2. 通知 active executor
    event = ACTIVE_RUNS.get(run_id)
    if event:
        event.set()
    else:
        logger.debug(f"Cancel: no active executor for run {run_id} (event not in ACTIVE_RUNS)")
