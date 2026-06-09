"""飞书 Webhook 渠道(详见 v2 plan §Phase D Task 25)。"""
import base64
import hashlib
import hmac
import time

import httpx

from .base import BaseChannel, NotificationPayload


class FeishuChannel(BaseChannel):
    channel_type = "feishu"

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config["webhook_url"]
        self.secret = config.get("secret")  # 可选,用于签名

    async def send(self, payload: NotificationPayload) -> bool:
        template = (
            "red"
            if payload.level == "critical"
            else "orange"
            if payload.level == "warning"
            else "blue"
        )
        data = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": payload.title},
                    "template": template,
                },
                "elements": [
                    {"tag": "markdown", "content": payload.body},
                ],
            },
        }
        if self.secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{self.secret}"
            hmac_code = hmac.new(
                string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
            ).digest()
            data["timestamp"] = timestamp
            data["sign"] = base64.b64encode(hmac_code).decode("utf-8")

        async with httpx.AsyncClient() as client:
            r = await client.post(self.webhook_url, json=data, timeout=10.0)
        return r.status_code == 200 and r.json().get("code", 0) == 0

    async def test(self) -> bool:
        return await self.send(
            NotificationPayload(
                title="MinBook 飞书通知测试",
                body="如果看到这条卡片,说明飞书 Webhook 配置正确。",
            )
        )
