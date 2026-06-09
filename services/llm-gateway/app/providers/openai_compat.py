"""OpenAI 兼容协议适配器(详见 v2 plan §Phase B Task 11)。

覆盖:OpenAI / DeepSeek / 智谱(zhipu) / Moonshot / Qwen。
所有这些服务都暴露 /chat/completions 兼容端点,可以用同一份代码。
"""
import os
import time
from decimal import Decimal
from typing import AsyncIterator

from openai import AsyncOpenAI

from minbook_common.models import LLMChatRequest, LLMChatResponse
from minbook_otel.llm_span import llm_call_span, record_llm_response, record_llm_error

from .base import BaseProvider


class OpenAICompatProvider(BaseProvider):
    def __init__(self, name: str, default_base: str, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.default_base = default_base
        # API key 优先从 kwargs,其次 {NAME}_API_KEY 环境变量,最后 OPENAI_API_KEY
        self.api_key = (
            self.api_key
            or os.environ.get(f"{name.upper()}_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        self.base_url = (
            self.base_url
            or os.environ.get(f"{name.upper()}_BASE_URL")
            or default_base
        )
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=120.0,
            )
        return self._client

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
            start = time.time()
            response = await client.chat.completions.create(
                model=request.model,
                messages=request.messages,  # type: ignore[arg-type]
                temperature=request.temperature,
                max_tokens=request.max_tokens or None,
                stream=False,
            )
            latency_ms = int((time.time() - start) * 1000)

            usage = response.usage
            cost = float(
                self.estimate_cost(
                    usage.prompt_tokens, usage.completion_tokens, request.model
                )
            )

            record_llm_response(
                span,
                usage.prompt_tokens,
                usage.completion_tokens,
                cost,
                latency_ms,
                finish_reason=response.choices[0].finish_reason or "stop",
            )
            return LLMChatResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                finish_reason=response.choices[0].finish_reason or "stop",
                usage={
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
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
        stream = await client.chat.completions.create(
            model=request.model,
            messages=request.messages,  # type: ignore[arg-type]
            temperature=request.temperature,
            max_tokens=request.max_tokens or None,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def estimate_cost(
        self, prompt_tokens: int, completion_tokens: int, model: str
    ) -> Decimal:
        """成本估算:从 llm.llm_providers 表读(详见 §12 §1.3)。

        DB 不可用时回落到 0(避免阻塞调用)。
        """
        try:
            from ..db import fetch_provider_cost
            return fetch_provider_cost(self.name, model, prompt_tokens, completion_tokens)
        except Exception:
            return Decimal(0)
