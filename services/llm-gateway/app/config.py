"""LLM Gateway 配置(详见 v2 plan §11 §6.1)。"""
from minbook_common.config import Settings


class LLMGatewaySettings(Settings):
    service_name: str = "llm-gateway"
    service_version: str = "0.1.0"

    # 幂等性缓存 TTL(24h,详见 §11 §6.1)
    llm_idempotency_ttl_seconds: int = 86400

    # LLM 调用超时
    llm_call_default_timeout_seconds: int = 120
    llm_call_streaming_chunk_timeout_seconds: int = 60


def get_settings() -> LLMGatewaySettings:
    return LLMGatewaySettings()
