"""ObserverAgent 单元测试。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.observer import ObserverAgent
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
async def test_observer_extracts_facts(monkeypatch):
    """LLM 返 JSON delta → 解析,只保留允许的 delta_targets key。"""
    import json
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    delta = {
        "current_state": {"chapter_progress": 5, "last_event": "Alice 找到剑"},
        "character_matrix": {"updates": [{"name": "Alice", "status": "armed"}]},
        "pending_hooks": {"new_hooks": ["剑的来历"]},
        "unknown_key_should_be_ignored": {"foo": "bar"},
    }

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": json.dumps(delta),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 800, "completion_tokens": 100},
                "latency_ms": 600,
                "cost_usd": 0.005,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = ObserverAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "content": "Alice 找到了锈迹斑斑的剑。",
                "chapter_number": 5,
            },
        )
    )

    assert output.status == "ok", output.error
    assert "current_state" in output.result["delta"]
    assert "character_matrix" in output.result["delta"]
    assert "unknown_key_should_be_ignored" in output.result["ignored_keys"]
    assert "current_state" in output.result["affected_files"]


@pytest.mark.asyncio
async def test_observer_missing_content_returns_error():
    """缺 content → status=error,不入 LLM。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = ObserverAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(AgentInput(book_id=book_id, book_settings={}))

    assert output.status == "error"
    assert "missing 'content'" in (output.error or "")
