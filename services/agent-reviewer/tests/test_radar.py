"""RadarAgent 单元测试(LLM 趋势 + 缓存 + NATS 事件,均做优雅降级测试)。"""
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.radar import RadarAgent
from minbook_common.agents.base import AgentInput


class _StubMemory:
    @property
    def pool(self):
        raise RuntimeError("no pool (stub)")

    async def recall(self, *a, **kw):
        return []

    async def load_procedural(self, *a, **kw):
        return None


@pytest.mark.asyncio
@respx.mock
async def test_radar_writes_to_radar_cache_via_stub(monkeypatch):
    """memory.pool 不可用 → 优雅降级,cache_id=None,trends 仍返。"""
    import json
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    llm_json = {
        "trends": [
            {"topic": "重生复仇", "heat": 0.9, "source": "qidian", "note": "持续高位"},
            {"topic": "系统穿越", "heat": 0.7, "source": "qidian", "note": "稳定"},
        ],
    }

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": json.dumps(llm_json),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 200, "completion_tokens": 80},
                "latency_ms": 500,
                "cost_usd": 0.003,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = RadarAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"genre": "玄幻", "platform": "起点", "top_n": 5},
        )
    )

    # LLM 返了 trends,即使缓存失败也返 ok
    assert output.status == "ok", output.error
    assert output.result["trend_count"] == 2
    assert output.result["trends"][0]["topic"] == "重生复仇"
    # cache_id 因为 pool 不可用 = None
    assert output.result["cache_id"] is None
    # NATS publish 在内存里会尝试但 nats 不可达,published=False
    assert output.result["published"] is False
    assert output.result["publish_error"] is not None


@pytest.mark.asyncio
@respx.mock
async def test_radar_falls_back_when_llm_fails(monkeypatch):
    """LLM 不可用 → fallback 趋势。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    # 让 LLM 端点返 500
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(500, json={"error": "upstream down"})
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    agent = RadarAgent(llm, None, _StubMemory(), prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"genre": "科幻"},
        )
    )

    # LLM 失败时,fallback trends 也应被返
    # 注:fallback 仍然让 status=ok(因为 trends 不空),仅 trends[0].source 标记为 "fallback"
    assert output.status == "ok"
    assert output.result["trend_count"] >= 1
    assert output.result["trends"][0]["source"] == "fallback"
