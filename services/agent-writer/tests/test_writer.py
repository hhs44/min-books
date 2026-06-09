"""WriterAgent 单元测试(用 respx mock llm-gateway)。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.writer import WriterAgent
from minbook_common.agents.base import AgentInput


class _StubMemory:
    """memory 桩:recall 返空、store/load_procedural 不抛。"""

    async def recall(self, *a, **kw):
        return []

    async def store_episode(self, *a, **kw):
        return "stub-id"

    async def load_procedural(self, *a, **kw):
        return None


def _wrap_recall_for_baseagent(memory):
    """BaseAgent.recall_context 调用 memory.recall(service=..., book_id=..., query=..., top_k=...)
    我们的桩签名兼容,不用再包。"""
    return memory


@pytest.mark.asyncio
@respx.mock
async def test_writer_generates_draft_within_range(monkeypatch):
    """字数在 [min, max] 区间 → needs_length_normalization=False。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    # 生成约 3000 字 — 在默认 [2550, 3450] 范围内
    draft = "正" * 3000
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": draft,
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 100, "completion_tokens": 3000},
                "latency_ms": 1500,
                "cost_usd": 0.02,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")

    agent = WriterAgent(llm, state_client=None, memory_client=_StubMemory(), prompt_loader=prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "genre": "科幻",
                "length_governance": {
                    "target_chapter_words": 3000,
                    "min_chapter_words": 2550,
                    "max_chapter_words": 3450,
                },
                "compiled_context": {"chapter_number": 1},
                "rule_stack": ["target_chapter_words: 3000"],
            },
        )
    )

    assert output.status == "ok", output.error
    assert output.result["word_count"] == 3000
    assert output.result["needs_length_normalization"] is False
    assert output.result["target_words"] == 3000


@pytest.mark.asyncio
@respx.mock
async def test_writer_flags_length_normalization_when_too_short(monkeypatch):
    """字数远低于 min → needs_length_normalization=True。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    # 只 500 字,远低于默认 [2550, 3450]
    short = "短" * 500
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": short,
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 100, "completion_tokens": 500},
                "latency_ms": 800,
                "cost_usd": 0.005,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = WriterAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"length_governance": {"target_chapter_words": 3000}},
        )
    )

    assert output.status == "ok"
    assert output.result["word_count"] == 500
    assert output.result["needs_length_normalization"] is True
