"""LLM chat 端点(详见 v2 plan §Phase B Task 16)。

- POST /internal/llm/chat
- 支持 Idempotency-Key(Redis 24h 缓存)
- 接受 5 个 X-* 跟踪 header
- OTel span + cost 记录
"""
import logging

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from minbook_common.models import LLMChatRequest, LLMChatResponse
from opentelemetry import trace

from ..cache import get_cached, set_cached
from ..config import get_settings
from ..db import record_llm_call
from ..providers.registry import get_provider

router = APIRouter()
settings = get_settings()
log = logging.getLogger(__name__)


def _resolve_provider_name(body: LLMChatRequest) -> str:
    """优先 body.provider;否则从 model 推断('gpt-*' → openai, 'claude-*' → anthropic)。"""
    if hasattr(body, "provider") and getattr(body, "provider", None):
        return getattr(body, "provider")
    model = (body.model or "").lower()
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("deepseek"):
        return "deepseek"
    if model.startswith("glm"):
        return "zhipu"
    if model.startswith("moonshot") or "kimi" in model:
        return "moonshot"
    if model.startswith("qwen") or "qwq" in model:
        return "qwen"
    if model.startswith("llama") or model.startswith("mistral"):
        return "ollama"
    return "openai"


@router.post("/chat", response_model=None)
async def chat(
    body: LLMChatRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    x_book_id: str | None = Header(None, alias="X-Book-Id"),
    x_pipeline_run_id: str | None = Header(None, alias="X-Pipeline-Run-Id"),
    x_task_id: str | None = Header(None, alias="X-Task-Id"),
    x_agent_id: str | None = Header(None, alias="X-Agent-Id"),
    x_node_id: str | None = Header(None, alias="X-Node-Id"),
):
    """调 LLM(支持幂等键)。"""
    # 1. 查缓存
    cached = await get_cached(idempotency_key, body)
    if cached is not None:
        return cached

    # 2. 解析 provider
    provider_name = _resolve_provider_name(body)
    provider = get_provider(provider_name)

    # 当前 trace id(供 llm.llm_calls.trace_id)
    span = trace.get_current_span()
    sc = span.get_span_context() if span else None
    trace_id = format(sc.trace_id, "032x") if sc and sc.trace_id else None

    # 3. 调 LLM
    try:
        if body.stream:
            async def stream_gen():
                async for chunk in provider.stream(body):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(stream_gen(), media_type="text/event-stream")
        else:
            response: LLMChatResponse = await provider.chat(body)

        # 4. 缓存
        if idempotency_key:
            await set_cached(
                idempotency_key, body, response,
                ttl=settings.llm_idempotency_ttl_seconds,
            )

        # 5. 记录(fire-and-forget)
        await record_llm_call(
            book_id=x_book_id,
            pipeline_run_id=x_pipeline_run_id,
            task_id=x_task_id,
            agent_id=x_agent_id,
            node_id=x_node_id,
            provider=provider.name,
            model=body.model,
            endpoint=provider.base_url,
            prompt_tokens=response.usage.get("prompt_tokens", 0),
            completion_tokens=response.usage.get("completion_tokens", 0),
            latency_ms=response.latency_ms,
            cost_estimate=response.cost_usd,
            success=True,
            error_type=None,
            trace_id=trace_id,
        )
        return response
    except Exception as e:
        await record_llm_call(
            book_id=x_book_id,
            pipeline_run_id=x_pipeline_run_id,
            task_id=x_task_id,
            agent_id=x_agent_id,
            node_id=x_node_id,
            provider=provider_name,
            model=body.model,
            endpoint=None,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0,
            cost_estimate=0,
            success=False,
            error_type=type(e).__name__,
            trace_id=trace_id,
        )
        log.exception("LLM call failed: provider=%s model=%s", provider_name, body.model)
        raise
