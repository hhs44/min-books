"""agent-reviewer-service 配置。"""
from minbook_common.config import Settings


class AgentReviewerSettings(Settings):
    service_name: str = "agent-reviewer-service"
    service_version: str = "0.3.0"
    service_port: int = 8005
    service_short: str = "reviewer"


def get_settings() -> AgentReviewerSettings:
    return AgentReviewerSettings()
