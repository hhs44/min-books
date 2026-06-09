"""LLM Provider 抽象基类(详见 v2 plan §Phase B Task 10)。"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import AsyncIterator

from minbook_common.models import LLMChatRequest, LLMChatResponse


class LLMUsage:
    """Token 用量统计(轻量级,只暴露两个字段)。"""

    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class BaseProvider(ABC):
    """所有 LLM 适配器继承此类。"""

    name: str = "base"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.extra = kwargs

    @abstractmethod
    async def chat(self, request: LLMChatRequest) -> LLMChatResponse: ...

    @abstractmethod
    async def stream(self, request: LLMChatRequest) -> AsyncIterator[str]: ...

    @abstractmethod
    def estimate_cost(
        self, prompt_tokens: int, completion_tokens: int, model: str
    ) -> Decimal: ...
