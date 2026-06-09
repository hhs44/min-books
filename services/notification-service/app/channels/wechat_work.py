"""企业微信 Webhook 渠道(详见 v2 plan §Phase D Task 26)。"""
import httpx

from .base import BaseChannel, NotificationPayload


class WeChatWorkChannel(BaseChannel):
    channel_type = "wechat_work"

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config["webhook_url"]

    async def send(self, payload: NotificationPayload) -> bool:
        # 企业微信 markdown 类型
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {payload.title}\n\n{payload.body}",
            },
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(self.webhook_url, json=data, timeout=10.0)
        return r.status_code == 200 and r.json().get("errcode", 0) == 0

    async def test(self) -> bool:
        return await self.send(
            NotificationPayload(
                title="MinBook 企微通知测试",
                body="如果看到这条 markdown,说明企微 Webhook 配置正确。",
            )
        )
