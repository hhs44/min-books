"""通用 Webhook 渠道(详见 v2 plan §Phase D Task 27)。

带可选 HMAC-SHA256 签名 (X-MinBook-Signature header)。
"""
import hashlib
import hmac
import json

import httpx

from .base import BaseChannel, NotificationPayload


class WebhookChannel(BaseChannel):
    channel_type = "webhook"

    def __init__(self, config: dict):
        super().__init__(config)
        self.url = config["url"]
        self.secret = config.get("secret")  # 可选,用于 HMAC 签名
        self.headers = config.get("headers", {})

    def _sign(self, body: bytes) -> str:
        if not self.secret:
            return ""
        return hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()

    async def send(self, payload: NotificationPayload) -> bool:
        body_bytes = payload.model_dump_json().encode("utf-8")
        headers = {**self.headers, "Content-Type": "application/json"}
        if self.secret:
            headers["X-MinBook-Signature"] = self._sign(body_bytes)

        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.url, content=body_bytes, headers=headers, timeout=10.0
            )
        return 200 <= r.status_code < 300

    async def test(self) -> bool:
        return await self.send(
            NotificationPayload(
                title="MinBook Webhook 测试",
                body="如果你的服务端收到这条消息,说明 Webhook 配置正确。",
            )
        )
