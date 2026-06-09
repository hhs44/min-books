"""agent-writer-service 配置。"""
from minbook_common.config import Settings


class AgentWriterSettings(Settings):
    service_name: str = "agent-writer-service"
    service_version: str = "0.3.0"
    service_port: int = 8004
    service_short: str = "writer"


def get_settings() -> AgentWriterSettings:
    return AgentWriterSettings()
