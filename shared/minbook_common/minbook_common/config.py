"""所有服务共用的基础配置(各服务可继承扩展)。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有服务共用的基础配置(各服务可继承扩展)。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 通用
    deploy_env: str = "dev"
    log_level: str = "INFO"
    service_name: str = "unknown"
    service_version: str = "0.1.0"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "minbook"
    postgres_user: str = "minbook"
    postgres_password: str = "minbook_dev"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # NATS
    nats_url: str = "nats://localhost:4222"

    # OTel
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # 鉴权
    jwt_secret: str = ""
    service_secret: str = ""
    allow_loopback_bypass: bool = True

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def get_settings() -> Settings:
    return Settings()
