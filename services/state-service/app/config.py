"""State Service 配置(详见 v2 plan §Phase C Task 17)。"""
from minbook_common.config import Settings


class StateServiceSettings(Settings):
    service_name: str = "state-service"
    service_version: str = "0.1.0"


def get_settings() -> StateServiceSettings:
    return StateServiceSettings()
