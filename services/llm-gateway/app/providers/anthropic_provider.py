"""Anthropic Claude 适配器(独立协议,Messages API,详见 v2 plan §Phase B Task 12)。"""
import os
import time
from decimal import Decimal
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from minbook_common.models import LLMChatRequest, LLMChatResponse
from minbook_otel.llm_span import llm_call_span, record_llm_response, record_llm_error

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key, timeout=120.0)
        return self._client

    @staticmethod
    def _split_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Anthropic 协议:system 消息单独抽离,其它平铺。"""
        system_msg = None
        rest = []
        for m in messages:
            if m.get("role") == "system":
                system_msg = m.get("content")
            else:
                rest.append({"role": m.get("role"), "content": m.get("content")})
        return system_msg, rest

    async def chat(self, request: LLMChatRequest) -> LLMChatResponse:
        span = llm_call_span(
            request.model,
            self.name,
            stream=False,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        try:
            client = self._get_client()
            system_msg, messages = self._split_messages(request.messages)

            start = time.time()
            response = await client.messages.create(
                model=request.model,
                system=system_msg,
                messages=messages,  # type: ignore[arg-type]
                temperature=request.temperature,
                max_tokens=request.max_tokens or 4096,
            )
            latency_ms = int((time.time() - start) * 1000)

            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            cost = float(
                self.estimate_cost(prompt_tokens, completion_tokens, request.model)
            )

            record_llm_response(
                span,
                prompt_tokens,
                completion_tokens,
                cost,
                latency_ms,
                finish_reason=response.stop_reason or "stop",
            )
            content = ""
            if response.content:
                content = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
            return LLMChatResponse(
                content=content,
                model=response.model,
                finish_reason=response.stop_reason or "stop",
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
                latency_ms=latency_ms,
                cost_usd=Decimal(str(cost)),
            )
        except Exception as e:
            record_llm_error(span, e)
            raise
        finally:
            span.end()

    async def stream(self, request: LLMChatRequest) -> AsyncIterator[str]:
        client = self._get_client()
        system_msg, messages = self._split_messages(request.messages)
        async with client.messages.stream(
            model=request.model,
            system=system_msg,
            messages=messages,  # type: ignore[arg-type]
            temperature=request.temperature,
            max_tokens=request.max_tokens or 4096,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def estimate_cost(
        self, prompt_tokens: int, completion_tokens: int, model: str
    ) -> Decimal:
        try:
            from ..db import fetch_provider_cost
            return fetch_provider_cost(self.name, model, prompt_tokens, completion_tokens)
        except Exception:
            return Decimal(0)
