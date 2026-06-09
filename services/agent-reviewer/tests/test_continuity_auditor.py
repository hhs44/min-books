"""ContinuityAuditor 单元测试(用 respx mock llm-gateway + 桩 state/memory)。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.continuity_auditor import (
    AuditIssue,
    AuditReport,
    ContinuityAuditor,
)
from minbook_common.agents.base import AgentInput


class _StubState:
    """state 桩:返 7 个真相文件占位。"""

    async def get_truth(self, book_id, file_type):
        if file_type == "character_matrix":
            return {
                "version": 1,
                "content": {"characters": [{"name": "Alice"}, {"name": "Bob"}]},
            }
        if file_type == "current_state":
            return {
                "version": 3,
                "content": {"chapter_progress": 1, "last_event": "init"},
            }
        return {"version": 1, "content": {}}


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
async def test_continuity_auditor_with_mock(monkeypatch):
    """LLM 返合法 AuditReport JSON → 解析成功,status=ok。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    audit_json = {
        "issues": [
            {
                "severity": "major",
                "dimension": "character_voice",
                "description": "Alice 突然用粗俗语气",
                "location": "par 5",
                "suggestion": "恢复温和语气",
            },
        ],
        "overall_score": 0.72,
        "critical_count": 0,
        "major_count": 1,
        "minor_count": 0,
    }

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": __import__("json").dumps(audit_json),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 1500, "completion_tokens": 200},
                "latency_ms": 1200,
                "cost_usd": 0.015,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = ContinuityAuditor(llm, _StubState(), _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "content": "Alice 走向城堡,她说道: '给老子滚!'",
                "chapter_number": 3,
            },
        )
    )

    assert output.status == "ok", output.error
    assert output.result["overall_score"] == 0.72
    assert output.result["major_count"] == 1
    assert output.result["critical_count"] == 0
    assert len(output.result["issues"]) == 1
    assert output.result["issues"][0]["dimension"] == "character_voice"


@pytest.mark.asyncio
@respx.mock
async def test_continuity_auditor_handles_bad_json(monkeypatch):
    """LLM 返非 JSON → status=error,带 raw_content 截断。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": "这是一些非 JSON 输出,LLM 跑飞了",
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "latency_ms": 500,
                "cost_usd": 0.001,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = ContinuityAuditor(llm, _StubState(), _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "任何内容", "chapter_number": 1},
        )
    )

    assert output.status == "error"
    assert "Parse failed" in (output.error or "")
    assert "raw_content" in output.result


@pytest.mark.asyncio
@respx.mock
async def test_continuity_auditor_dimensions_count():
    """ContinuityAuditor.DIMENSIONS 应有 33 个(与 v2 spec §1.2 一致)。"""
    agent = ContinuityAuditor(None, None, _StubMemory(), None)
    assert len(agent.DIMENSIONS) == 33
    assert "character_consistency" in agent.DIMENSIONS
    assert "foreshadowing_payoff" in agent.DIMENSIONS
    assert "symbolic_coherence" in agent.DIMENSIONS
