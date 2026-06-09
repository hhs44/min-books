"""Channel registry:把 4 个 channel 实现导出。"""
from .base import BaseChannel, NotificationPayload
from .feishu import FeishuChannel
from .telegram import TelegramChannel
from .wechat_work import WeChatWorkChannel
from .webhook import WebhookChannel

__all__ = [
    "BaseChannel",
    "NotificationPayload",
    "TelegramChannel",
    "FeishuChannel",
    "WeChatWorkChannel",
    "WebhookChannel",
]

CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "telegram": TelegramChannel,
    "feishu": FeishuChannel,
    "wechat_work": WeChatWorkChannel,
    "webhook": WebhookChannel,
}
