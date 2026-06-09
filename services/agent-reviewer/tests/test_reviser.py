"""ReviserAgent 单元测试。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.reviser import ReviserAgent
from minbook_common.agents.base import AgentInput


class _StubMemory:
    async def recall(self, *a, **kw):
        return []

    async def store_episode(self, *a, **kw):
        return "stub-id"

    async def load_procedural(self, *a, **kw):
        return None

    @property
    def pool(self):
        raise RuntimeError("no pool (stub)")


@pytest.mark.asyncio
@respx.mock
async def test_reviser_passes_through_to_llm(monkeypatch):
    """传 content + issues,LLM 返 JSON → 解析为 revised_content + changes_made。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": (
                    '{"revised_content": "修复后章节", '
                    '"changes_made": ["修复角色语气", "补充时间线"]}'
                ),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 200, "completion_tokens": 100},
                "latency_ms": 800,
                "cost_usd": 0.01,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = ReviserAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "content": "原章节",
                "issues": [
                    {"severity": "major", "dimension": "character_voice",
                     "description": "X", "location": "par 1", "suggestion": "Y"},
                ],
            },
        )
    )

    assert output.status == "ok", output.error
    assert output.result["revised_content"] == "修复后章节"
    assert "修复角色语气" in output.result["changes_made"]
    assert output.result["issues_addressed"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_reviser_no_issues_returns_content_unchanged(monkeypatch):
    """issues 为空时,不走 LLM,直接返原 content。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    # LLM 端点不应被调用
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(200, json={"content": "should not be called"})
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = ReviserAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "原章节", "issues": []},
        )
    )

    assert output.status == "ok"
    assert output.result["revised_content"] == "原章节"
    assert output.result["changes_made"] == []
    assert output.result["issues_addressed"] == 0
