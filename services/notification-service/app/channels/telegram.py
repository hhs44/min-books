"""Telegram Bot 渠道(详见 v2 plan §Phase D Task 24)。"""
import httpx

from .base import BaseChannel, NotificationPayload


class TelegramChannel(BaseChannel):
    channel_type = "telegram"

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config["bot_token"]
        self.chat_id = config["chat_id"]

    async def send(self, payload: NotificationPayload) -> bool:
        text = f"*{payload.title}*\n\n{payload.body}"
        if payload.level == "critical":
            text = "🚨 " + text
        elif payload.level == "warning":
            text = "⚠️ " + text

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10.0,
            )
        return r.status_code == 200

    async def test(self) -> bool:
        return await self.send(
            NotificationPayload(
                title="MinBook 通知测试",
                body="如果看到这条消息,说明 Telegram 渠道配置正确。",
            )
        )
