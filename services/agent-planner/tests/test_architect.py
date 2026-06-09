"""ArchitectAgent 单元测试(用 respx mock llm-gateway)。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.architect import ArchitectAgent
from minbook_common.agents.base import AgentInput


@pytest.mark.asyncio
@respx.mock
async def test_architect_generates_story_bible(monkeypatch):
    """ArchitectAgent 调 LLM → 解析 JSON → 返回 story_bible + 写 2 真相文件。"""
    book_id = uuid4()

    # Mock LLM Gateway 响应
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": '{"story_bible": {"world": "test world", "core_setting": "magic school", "timeline": "modern"}, "style_guide": {"narrative_pov": "third", "tense": "past"}, "book_rules": ["no anachronism"], "character_matrix": {"characters": [{"name": "Alice", "role": "protagonist"}]}, "length_governance": {"target_chapter_words": 3000}}',
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "latency_ms": 1000,
                "cost_usd": 0.001,
            },
        )
    )

    # Mock state-service 写真相
    respx.put(
        f"http://state-service:8007/internal/state/{book_id}/truth/character_matrix"
    ).mock(return_value=Response(200, json={"version": 1}))
    respx.put(
        f"http://state-service:8007/internal/state/{book_id}/truth/current_state"
    ).mock(return_value=Response(200, json={"version": 1}))

    # 创建真实的 LLMClient + StateClient 实例(respx 会拦截它们的 HTTP)
    from minbook_common.clients.llm_client import LLMClient
    from minbook_common.clients.state_client import StateClient

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("STATE_SERVICE_URL", "http://state-service:8007")
    monkeypatch.setenv("SERVICE_SECRET", "")  # 跳过 HMAC

    llm = LLMClient(service_name="agent-planner-service")
    state = StateClient(service_name="agent-planner-service")

    # Stub:不需要真实 memory(ArchitectAgent 不调 memory)
    memory = type("M", (), {"recall": lambda *a, **k: [], "store_episode": lambda *a, **k: "x"})()
    from minbook_common.agents.prompt_loader import PromptLoader

    prompts = PromptLoader(template_dir="prompts")

    agent = ArchitectAgent(llm, state, memory, prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"title": "测试", "genre": "科幻", "language": "zh"},
            current_focus="建书",
        )
    )

    assert output.status == "ok", f"unexpected status: {output.status}, error: {output.error}"
    assert "story_bible" in output.result
    assert output.result["story_bible"]["world"] == "test world"
    assert output.result["length_governance"]["target_chapter_words"] == 3000
    assert output.metrics["cost_usd"] == 0.001
