"""FoundationReviewerAgent 单元测试(respx mock LLM)。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.foundation_reviewer import FoundationReviewerAgent
from minbook_common.agents.base import AgentInput


@pytest.mark.asyncio
@respx.mock
async def test_foundation_reviewer_returns_verdict(monkeypatch):
    """审核 Agent 调 LLM → 解析 FoundationReview → 返 verdict/issues/score。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": '{"verdict": "PASS", "issues": [], "overall_score": 0.95}',
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 200, "completion_tokens": 20},
                "latency_ms": 800,
                "cost_usd": 0.0005,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-planner-service")
    state = None  # FoundationReviewerAgent 不调 state
    memory = type("M", (), {"recall": lambda *a, **k: []})()
    prompts = PromptLoader(template_dir="prompts")

    agent = FoundationReviewerAgent(llm, state, memory, prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "architect_output": {
                    "story_bible": {"world": "test"},
                    "style_guide": {"narrative_pov": "third"},
                    "book_rules": ["rule 1"],
                    "character_matrix": {"characters": []},
                    "length_governance": {"target_chapter_words": 3000},
                },
            },
        )
    )

    assert output.status == "ok"
    assert output.result["verdict"] == "PASS"
    assert output.result["issues"] == []
    assert output.result["overall_score"] == 0.95


@pytest.mark.asyncio
async def test_foundation_reviewer_missing_input():
    """没传 architect_output → 返 error。"""
    from minbook_common.agents.prompt_loader import PromptLoader

    prompts = PromptLoader(template_dir="prompts")
    agent = FoundationReviewerAgent(None, None, None, prompts)
    output = await agent.run(AgentInput(book_id=uuid4(), book_settings={}))
    assert output.status == "error"
    assert "architect_output" in output.error
