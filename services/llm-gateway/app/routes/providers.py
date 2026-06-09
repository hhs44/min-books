"""LLM provider 列表 / 测试端点(详见 v2 plan §Phase B Task 16)。

- GET  /internal/llm/providers  → 列出所有 provider 名(供 gateway 转发)
- GET  /internal/llm/models     → 列出可用模型(带定价)
- POST /internal/llm/test       → 用 mini prompt 测试 provider 连接
"""
from fastapi import APIRouter

from minbook_common.models import LLMChatRequest

from ..db import acquire
from ..providers.registry import get_provider

router = APIRouter()


@router.get("/providers")
async def list_providers():
    """列出已配置的 LLM provider(去重,从 llm.llm_providers 表读)。"""
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT provider FROM llm.llm_providers
               ORDER BY provider"""
        )
    return [r["provider"] for r in rows]


@router.get("/models")
async def list_models():
    """列出可用模型(含定价)。"""
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT provider, model,
                      cost_per_1k_input_tokens AS input_cost,
                      cost_per_1k_output_tokens AS output_cost
               FROM llm.llm_providers
               WHERE effective_from <= CURRENT_DATE
               ORDER BY provider, model"""
        )
    return [dict(r) for r in rows]


@router.post("/test")
async def test_connection(body: dict):
    """用 mini prompt 测试 provider 连接。"""
    provider_name = body.get("provider", "openai")
    model = body.get("model", "gpt-4o-mini")
    api_key = body.get("api_key")
    base_url = body.get("base_url")

    try:
        provider = get_provider(provider_name, api_key=api_key, base_url=base_url)
        response = await provider.chat(
            LLMChatRequest(
                model=model,
                messages=[{"role": "user", "content": "say 'ok' in 1 word"}],
                max_tokens=5,
            )
        )
        return {
            "status": "ok",
            "response": response.content,
            "latency_ms": response.latency_ms,
            "model": response.model,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
