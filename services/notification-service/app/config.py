"""Notification Service 配置(详见 v2 plan §Phase D)。"""
from minbook_common.config import Settings


class NotificationSettings(Settings):
    service_name: str = "notification-service"
    service_version: str = "0.1.0"


def get_settings() -> NotificationSettings:
    return NotificationSettings()
