"""NATS 告警事件订阅(详见 v2 plan §Phase D Task 25)。

订阅:
  - minbook.alert.>               所有 alert 事件
  - minbook.pipeline.chapter.failed  章节生成失败
"""
import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from minbook_common.nats_client import MinBookNATS

logger = logging.getLogger(__name__)


async def start_consumer(nats: MinBookNATS):
    """启动所有订阅。"""
    # 确保 JetStream stream 存在(v2 spec §3.2.5)
    await nats.ensure_stream()
    # 订阅所有 alert 事件
    await nats.subscribe("minbook.alert.>", _handle_event("alert"))
    # 订阅 chapter.failed(独立 subject,虽然 alert.> 通常已包含,但显式订阅更安全)
    await nats.subscribe("minbook.pipeline.chapter.failed", _handle_event("chapter_failed"))
    logger.info("notification-service NATS consumer started (alert.* + pipeline.chapter.failed)")


def _handle_event(source: str):
    """返回一个 NATS event handler。"""

    async def handler(event_data: dict[str, Any]):
        # event_data 是 MinBookEvent.model_dump() 的产物
        data = event_data.get("data", {}) or {}
        book_id = data.get("book_id")
        if not book_id:
            logger.debug(f"dropping {source} event without book_id: {event_data.get('event_type')}")
            return

        title = event_data.get("event_type", source)
        body = json.dumps(data, ensure_ascii=False, indent=2)
        level = data.get("level", "info")

        # 调内部 notify 端点逻辑
        try:
            from .routes.channels import notify

            await notify(UUID(book_id), {
                "title": f"[MinBook] {title}",
                "body": body,
                "level": level,
            })
        except Exception as e:
            # 通知失败不阻塞主流程(consumer 自己会 NACK + 重试)
            logger.warning(f"notify failed for {book_id} ({source}): {type(e).__name__}: {e}")

    return handler
