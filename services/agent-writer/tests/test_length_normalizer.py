"""LengthNormalizer 单元测试 — 含纯逻辑(<5% 跳过)和 LLM 调用分支。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.length_normalizer import LengthNormalizer
from minbook_common.agents.base import AgentInput


class _StubMemory:
    async def recall(self, *a, **kw):
        return []

    async def store_episode(self, *a, **kw):
        return "x"


@pytest.mark.asyncio
async def test_length_normalizer_skips_within_5pct():
    """偏差 < 5% → adjusted=False,不调 LLM。"""
    from minbook_common.agents.prompt_loader import PromptLoader

    prompts = PromptLoader(template_dir="prompts")
    # 不传 LLM client — 这条路径不应该触发 LLM
    agent = LengthNormalizer(None, None, _StubMemory(), prompts)

    content = "字" * 1000  # 1000 字
    output = await agent.run(
        AgentInput(
            book_id=uuid4(),
            book_settings={
                "content": content,
                "target_words": 1020,  # 偏差 2%,< 5% 阈值
            },
        )
    )

    assert output.status == "ok"
    assert output.result["adjusted"] is False
    assert output.result["content"] == content
    assert output.result["current_words"] == 1000


@pytest.mark.asyncio
@respx.mock
async def test_length_normalizer_compresses_when_over(monkeypatch):
    """偏差 ≥ 5% 且 content 太长 → 调 LLM 压缩。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    compressed = "压缩后" * 100  # 300 字
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": compressed,
                "model": "gpt-4o-mini",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 500, "completion_tokens": 200},
                "latency_ms": 600,
                "cost_usd": 0.001,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = LengthNormalizer(llm, None, _StubMemory(), prompts)

    content = "原文字符" * 200  # 800 字
    output = await agent.run(
        AgentInput(
            book_id=uuid4(),
            book_settings={
                "content": content,
                "target_words": 300,  # 偏差 ~62%
            },
        )
    )

    assert output.status == "ok"
    assert output.result["adjusted"] is True
    assert output.result["new_word_count"] == len(compressed)
    assert output.result["direction"] == "compress"
