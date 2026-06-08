"""LLM 调用专用 span(详见 §10 §3.3)。"""
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

_tracer = trace.get_tracer("minbook.llm")


def llm_call_span(model: str, provider: str, **attrs: Any):
    """LLM 调用的 span context manager,所有 agent 服务必须用。"""
    span = _tracer.start_span("llm.call", attributes={
        "llm.model": model,
        "llm.provider": provider,
        "llm.stream": attrs.get("stream", False),
        "llm.temperature": float(attrs.get("temperature", 0.7)),
        "llm.max_tokens": int(attrs.get("max_tokens", 0)),
    })
    return span


def record_llm_response(
    span,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: int,
    finish_reason: str = "stop",
):
    span.set_attribute("llm.prompt_tokens", prompt_tokens)
    span.set_attribute("llm.completion_tokens", completion_tokens)
    span.set_attribute("llm.cost_usd", cost_usd)
    span.set_attribute("llm.latency_ms", latency_ms)
    span.set_attribute("llm.finish_reason", finish_reason)


def record_llm_error(span, error: Exception):
    span.record_exception(error)
    span.set_status(Status(StatusCode.ERROR))
    span.set_attribute("llm.error_type", type(error).__name__)
