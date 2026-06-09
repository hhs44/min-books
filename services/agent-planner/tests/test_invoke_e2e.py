"""agent-planner-service e2e invoke 测试(Phase E Task 2)。

模拟完整 agent invoke 链路:invoke → recall (memory) → get_truth (state) →
load_procedural → prompt render → LLM call (respx mock) → store_episode → return。

测试覆盖:PlannerAgent(章节意图生成)— 4 agents 中 LLM 链路最完整。
"""
from uuid import uuid4

import pytest
import respx
from httpx import Response


class _StubMemory:
    """memory 桩:track 调用 + 模拟真实行为。

    跟踪 recall/store_episode 调用次数,模拟 BaseAgent.recall_context 实际路径。
    """

    def __init__(self):
        self.recall_calls = 0
        self.store_calls = 0

    async def recall(self, *a, **kw):
        self.recall_calls += 1
        return [{"id": "ep-1", "content": "过去的章节意图", "score": 0.85}]

    async def store_episode(self, *a, **kw):
        self.store_calls += 1
        return f"ep-{self.store_calls}"

    async def load_procedural(self, *a, **kw):
        return "作者偏好:三幕剧结构,每章结尾留钩子"


class _StubStateClient:
    """state 桩:跟踪 get_truth 调用,返回 mocked 真相数据。"""

    def __init__(self):
        self.get_calls = 0
        self.update_calls = 0

    async def get_truth(self, book_id, file_type):
        self.get_calls += 1
        if file_type == "current_state":
            return {"chapter_progress": 2, "last_event": "Alice 拿到入学信"}
        if file_type == "character_matrix":
            return {"characters": [{"name": "Alice", "role": "protagonist"}]}
        return {}

    async def update_truth(self, book_id, file_type, content, expected_version=None):
        self.update_calls += 1
        return {"version": self.update_calls}


@pytest.mark.asyncio
@respx.mock
async def test_planner_e2e_invoke_chain(monkeypatch):
    """PlannerAgent 完整链路。

    验证 6 件事:
      1. memory.recall 被调 1 次(拿到历史 episodes)
      2. state.get_truth 被调 2 次(current_state + character_matrix)
      3. LLM Gateway /internal/llm/chat 被调 1 次
      4. memory.store_episode 被调 1 次(写入新 episode)
      5. 返回 AgentOutput 含 ChapterIntent 字段对齐 schema
      6. metrics 含 cost_usd / tokens / latency_ms
    """
    from minbook_common.agents.base import AgentInput
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()
    chapter_number = 3

    import json
    # ChapterIntent schema:chapter_number / title / intent / key_events /
    #   characters_involved / emotional_arc / style_notes
    chapter_intent = {
        "chapter_number": chapter_number,
        "title": "Alice 踏入魔法学院",
        "intent": "Alice 抵达魔法学院,遇见导师 Merlin",
        "key_events": ["Alice 抵达学院", "遇见 Merlin", "获得第一件任务"],
        "characters_involved": ["Alice", "Merlin"],
        "emotional_arc": "期待 → 紧张 → 鼓舞",
        "style_notes": "用第三人称过去时,多感官描写学院外观",
    }
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": json.dumps(chapter_intent),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 800, "completion_tokens": 200},
                "latency_ms": 1200,
                "cost_usd": 0.012,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("STATE_SERVICE_URL", "http://state-service:8007")
    monkeypatch.setenv("SERVICE_SECRET", "")

    from app.agents.planner import PlannerAgent

    llm = LLMClient(service_name="agent-planner-service")
    prompts = PromptLoader(template_dir="prompts")
    memory = _StubMemory()
    state = _StubStateClient()

    agent = PlannerAgent(llm, state_client=state, memory_client=memory, prompt_loader=prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "story_bible": {"world": "魔法学院"},
                "current_state": {"chapter_progress": 2},
                "character_matrix": {"characters": [{"name": "Alice", "role": "protagonist"}]},
            },
            current_focus="生成第 3 章意图",
        )
    )

    # 1. status + result 字段对齐
    assert output.status == "ok", f"unexpected: {output.error}"
    assert output.result["chapter_number"] == chapter_number
    assert "Alice" in output.result["intent"]
    assert output.result["title"] == "Alice 踏入魔法学院"
    assert len(output.result["key_events"]) == 3
    assert "Alice" in output.result["characters_involved"]

    # 2. memory 链路
    assert memory.recall_calls == 1, f"expected 1 recall, got {memory.recall_calls}"
    assert memory.store_calls == 1, f"expected 1 store, got {memory.store_calls}"

    # 3. state 链路
    assert state.get_calls == 2, f"expected 2 get_truth calls, got {state.get_calls}"

    # 4. LLM 链路
    assert len(respx.calls) == 1

    # 5. metrics 完整
    assert output.metrics["cost_usd"] == 0.012
    assert output.metrics["tokens"]["completion_tokens"] == 200
    assert output.metrics["latency_ms"] == 1200