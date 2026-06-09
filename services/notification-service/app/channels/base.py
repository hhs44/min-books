"""Channel 抽象(详见 v2 plan §Phase D Task 23)。"""
from abc import ABC, abstractmethod

from pydantic import BaseModel


class NotificationPayload(BaseModel):
    """通知负载。"""

    title: str
    body: str
    level: str = "info"  # info | warning | critical
    book_id: str | None = None
    chapter_number: int | None = None
    details: dict | None = None


class BaseChannel(ABC):
    """所有 channel 必须实现的接口。"""

    channel_type: str = "base"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """发送一条通知;成功返回 True。"""

    @abstractmethod
    async def test(self) -> bool:
        """发一条测试消息;成功返回 True。"""
