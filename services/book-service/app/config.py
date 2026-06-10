"""Book Service 配置(详见 v6 plan §Phase B)。"""
from minbook_common.config import Settings


class BookServiceSettings(Settings):
    service_name: str = "book-service"
    service_version: str = "0.1.0"
    service_port: int = 8001


def get_settings() -> BookServiceSettings:
    return BookServiceSettings()
