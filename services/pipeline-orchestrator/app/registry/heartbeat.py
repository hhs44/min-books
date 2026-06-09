"""心跳监控:90s 无心跳 → inactive(详见 v2 §4.3 + v4 §Phase D Task 13)。"""
import asyncio
import logging

from .store import mark_stale_agents

logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    def __init__(self, inactive_threshold_seconds: int = 90, check_interval: int = 30):
        self.threshold = inactive_threshold_seconds
        self.check_interval = check_interval

    async def run_forever(self):
        while True:
            try:
                count = await mark_stale_agents(self.threshold)
                if count > 0:
                    logger.warning(f"Marked {count} agents as inactive (no heartbeat > {self.threshold}s)")
            except Exception as e:
                logger.exception(f"Heartbeat monitor error: {e}")
            await asyncio.sleep(self.check_interval)
