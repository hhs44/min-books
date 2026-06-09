"""NATS 客户端封装,统一事件发布/订阅。

使用 NATS JetStream durable consumer(v2 spec §3.2.5: stream 名 `minbook-events`)
以支持 ack/nak 重试语义。
"""
import json
import logging
from typing import Awaitable, Callable

import nats
from nats.aio.client import Client as NATSClient
from nats.errors import NotJSMessageError

from .models.event import MinBookEvent

logger = logging.getLogger(__name__)

# v2 spec §3.2.5:NATS JetStream stream 名(所有事件统一到 minbook-events)
STREAM_NAME = "minbook-events"


class MinBookNATS:
    def __init__(self, url: str, service_name: str, service_version: str = "0.1.0"):
        self.url = url
        self.service_name = service_name
        self.service_version = service_version
        self._nc: NATSClient | None = None
        self._js = None  # JetStream context (lazy)

    async def connect(self):
        self._nc = await nats.connect(self.url)
        return self._nc

    async def close(self):
        if self._nc:
            await self._nc.close()
            self._nc = None
            self._js = None

    @property
    def nc(self) -> NATSClient:
        if not self._nc:
            raise RuntimeError("NATS not connected")
        return self._nc

    @property
    def js(self):
        """JetStream context(惰性初始化,首次访问时创建)。"""
        if self._js is None:
            self._js = self.nc.jetstream()
        return self._js

    async def ensure_stream(self, stream: str = STREAM_NAME, subjects: list[str] | None = None):
        """确保 JetStream stream 存在(创建或更新 subjects)。v2 spec §3.2.5。

        Args:
            stream: stream 名,默认 `minbook-events`
            subjects: 关注的 subject 列表,默认 [`minbook.>`](所有 minbook 事件)
        """
        if subjects is None:
            subjects = ["minbook.>"]
        try:
            await self.js.stream_info(stream)
        except Exception:
            logger.info(f"creating JetStream stream '{stream}' with subjects={subjects}")
            await self.js.add_stream(name=stream, subjects=subjects)

    async def publish_event(
        self,
        subject: str,
        data: dict,
        trace_id: str | None = None,
        span_id: str | None = None,
    ):
        """发布 MinBookEvent 到 NATS subject(详见 v2 spec §3.2.4)。

        优先通过 JetStream 发布(支持消息持久化和 ack 追踪);
        失败时回落到普通 NATS publish(为了向后兼容,允许无 JS 的本地开发环境)。
        """
        event = MinBookEvent(
            event_type=subject,
            source_service=self.service_name,
            source_version=self.service_version,
            trace_id=trace_id,
            span_id=span_id,
            data=data,
        )
        payload = event.model_dump_json().encode("utf-8")
        try:
            await self.js.publish(subject, payload)
        except Exception as e:
            # JS 不可用时回落到普通 publish
            logger.debug(f"JetStream publish failed, falling back to core NATS: {e}")
            await self.nc.publish(subject, payload)
        await self.nc.flush()

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[dict], Awaitable[None]],
        queue: str | None = None,
        durable: str | None = None,
    ):
        """订阅 subject(必须用 JetStream 才能支持 ack/nak)。

        Args:
            subject: NATS subject,支持 wildcards(`>` / `*`)
            handler: 异步 handler,接收已解析的 dict
            queue: 队列组名(同组负载均衡,可选)
            durable: durable consumer 名(默认用 service_name + subject 派生)
        """
        # 默认 durable 名:service + subject 派生(避免跨服务冲突)
        if durable is None:
            durable = f"minbook-{self.service_name}-{subject}".replace(".", "-").replace(">", "all")[:64]

        async def cb(msg):
            try:
                data = json.loads(msg.data.decode("utf-8"))
            except Exception as e:
                logger.warning(f"event parse failed: {type(e).__name__}: {e}")
                try:
                    await msg.term()  # poison message:不要重试
                except NotJSMessageError:
                    pass
                return

            try:
                await handler(data)
            except Exception as e:
                logger.warning(f"event handler failed: {type(e).__name__}: {e}")
                try:
                    await msg.nak()
                except NotJSMessageError:
                    logger.debug("msg.nak() ignored: not a JS message")
                except Exception as nak_e:
                    logger.debug(f"msg.nak() failed: {type(nak_e).__name__}: {nak_e}")
                return

            try:
                await msg.ack()
            except NotJSMessageError:
                logger.debug("msg.ack() ignored: not a JS message")
            except Exception as e:
                logger.debug(f"msg.ack() failed: {type(e).__name__}: {e}")

        # 用 JetStream 订阅 → ack/nak 才会真正生效
        sub = await self.js.subscribe(
            subject,
            cb=cb,
            queue=queue,
            durable=durable,
            stream=STREAM_NAME,
        )
        return sub
