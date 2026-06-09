"""Gateway 专属配置(扩展 minbook_common.config.Settings)。"""
from pydantic import Field

from minbook_common.config import Settings


class GatewaySettings(Settings):
    service_name: str = "gateway"
    service_version: str = "0.1.0"

    # 下游服务 URL(在 docker-compose 网络内)
    pipeline_orchestrator_url: str = "http://pipeline-orchestrator:8002"
    state_service_url: str = "http://state-service:8007"
    llm_gateway_url: str = "http://llm-gateway:8006"
    notification_service_url: str = "http://notification-service:8008"
    book_service_url: str = "http://book-service:8001"  # v2 不实现,留 v3

    # 限流(默认 60 req/min/IP,可通过环境变量覆盖)
    rate_limit_per_minute: int = Field(default=60, ge=1)

    # i18n
    default_locale: str = "zh"
    supported_locales: list[str] = ["zh", "en", "ja"]


def get_settings() -> GatewaySettings:
    return GatewaySettings()
