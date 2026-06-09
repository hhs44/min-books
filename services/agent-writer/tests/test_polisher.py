"""PolisherAgent 单元测试。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.polisher import PolisherAgent
from minbook_common.agents.base import AgentInput


class _StubMemory:
    async def recall(self, *a, **kw):
        return []

    async def store_episode(self, *a, **kw):
        return "x"

    async def load_procedural(self, *a, **kw):
        return None


@pytest.mark.asyncio
@respx.mock
async def test_polisher_uses_draft_as_input(monkeypatch):
    """传 draft_content 进 book_settings,LLM 返 JSON → 解析为 PolisherOutput。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": (
                    '{"polished_content": "润色后的章节文字。", '
                    '"changes_made": ["改善节奏", "替换冗余形容词"]}'
                ),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 200, "completion_tokens": 50},
                "latency_ms": 700,
                "cost_usd": 0.008,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = PolisherAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "draft_content": "原始的章节文字。",
                "style_notes": "保持温暖叙述",
            },
        )
    )

    assert output.status == "ok", output.error
    assert output.result["polished_content"] == "润色后的章节文字。"
    assert "改善节奏" in output.result["changes_made"]


@pytest.mark.asyncio
@respx.mock
async def test_polisher_falls_back_when_json_parse_fails(monkeypatch):
    """LLM 返非 JSON → fallback:整段当作 polished_content,changes_made=[]。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    raw_text = "这只是纯文本输出,不是 JSON。"
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": raw_text,
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "latency_ms": 500,
                "cost_usd": 0.003,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = PolisherAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"draft_content": "原文"},
        )
    )

    assert output.status == "ok"
    assert output.result["polished_content"] == raw_text
    assert output.result["changes_made"] == []


@pytest.mark.asyncio
async def test_polisher_missing_draft():
    """没传 draft_content → 返 error。"""
    from minbook_common.agents.prompt_loader import PromptLoader

    prompts = PromptLoader(template_dir="prompts")
    agent = PolisherAgent(None, None, _StubMemory(), prompts)
    output = await agent.run(AgentInput(book_id=uuid4(), book_settings={}))
    assert output.status == "error"
    assert "draft_content" in output.error
