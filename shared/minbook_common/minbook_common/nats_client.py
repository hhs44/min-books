"""NATS 客户端封装,统一事件发布/订阅。"""
import json
from typing import Awaitable, Callable

import nats
from nats.aio.client import Client as NATSClient

from .models.event import MinBookEvent


class MinBookNATS:
    def __init__(self, url: str, service_name: str, service_version: str = "0.1.0"):
        self.url = url
        self.service_name = service_name
        self.service_version = service_version
        self._nc: NATSClient | None = None

    async def connect(self):
        self._nc = await nats.connect(self.url)
        return self._nc

    async def close(self):
        if self._nc:
            await self._nc.close()
            self._nc = None

    @property
    def nc(self) -> NATSClient:
        if not self._nc:
            raise RuntimeError("NATS not connected")
        return self._nc

    async def publish_event(
        self,
        subject: str,
        data: dict,
        trace_id: str | None = None,
        span_id: str | None = None,
    ):
        """发布 MinBookEvent 到 NATS subject(详见 v2 spec §3.2.4)。"""
        event = MinBookEvent(
            event_type=subject,
            source_service=self.service_name,
            source_version=self.service_version,
            trace_id=trace_id,
            span_id=span_id,
            data=data,
        )
        await self.nc.publish(subject, event.model_dump_json().encode("utf-8"))
        await self.nc.flush()

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[dict], Awaitable[None]],
        queue: str | None = None,
    ):
        async def cb(msg):
            try:
                data = json.loads(msg.data.decode("utf-8"))
                await handler(data)
                await msg.ack()
            except Exception:
                # 失败 NACK(交给 NATS 重试)
                await msg.nak()

        return await self.nc.subscribe(subject, cb=cb, queue=queue)
