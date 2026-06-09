"""agent-planner-service 配置。"""
from minbook_common.config import Settings


class AgentPlannerSettings(Settings):
    service_name: str = "agent-planner-service"
    service_version: str = "0.3.0"
    service_port: int = 8003
    # 用于 v3 Phase A:启动时注册的 service short name(短,用于 /internal/{short}/invoke)
    service_short: str = "planner"


def get_settings() -> AgentPlannerSettings:
    return AgentPlannerSettings()
