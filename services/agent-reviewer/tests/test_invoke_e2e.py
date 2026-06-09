"""agent-reviewer-service e2e invoke 测试(Phase E Task 2)。

模拟完整 invoke 链路:invoke → load 7 真相文件(state) → prompt render →
LLM call (respx mock) → 解析 JSON AuditReport → 写 reviewer.audit_history(memory) → return。

测试覆盖:ContinuityAuditor(33 维度审计)— 9 agents 中链路最完整的:
- 读 7 个真相文件
- 调 LLM 拿 AuditReport
- 写真集(reviewer.audit_history)
"""
from uuid import uuid4

import pytest
import respx
from httpx import Response


class _StubPool:
    """mock asyncpg.Pool:跟踪 INSERT reviewer.audit_history。"""

    def __init__(self):
        self.execute_calls = []
        self.acquire_count = 0

    def acquire(self):
        return _AcquireCtx(self)

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"


class _AcquireCtx:
    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        self.pool.acquire_count += 1
        return self.pool

    async def __aexit__(self, *a):
        return False


class _StubMemoryClient:
    def __init__(self):
        self.pool = _StubPool()
        self.recall_calls = 0
        self.store_calls = 0

    async def recall(self, *a, **kw):
        self.recall_calls += 1
        return []

    async def store_episode(self, *a, **kw):
        self.store_calls += 1
        return "stub-id"

    async def load_procedural(self, *a, **kw):
        return None


class _StubStateClient:
    """state 桩:跟踪 get_truth 调用(应被调 7 次,各文件类型)。"""

    def __init__(self):
        self.get_calls = 0
        self.file_types_seen = []

    async def get_truth(self, book_id, file_type):
        self.get_calls += 1
        self.file_types_seen.append(file_type)
        return {"_stub": True, "file_type": file_type, "data": f"sample_{file_type}"}

    async def update_truth(self, book_id, file_type, content, expected_version=None):
        return {"version": 1}


@pytest.mark.asyncio
@respx.mock
async def test_continuity_auditor_e2e_full_chain(monkeypatch):
    """ContinuityAuditor 完整链路:7 真相 → LLM → audit_history INSERT。

    验证 6 件事:
      1. state.get_truth 被调 7 次(7 真相文件)
      2. LLM Gateway 被调 1 次
      3. 返回 AuditReport 含 issues + counts + score
      4. memory.pool.execute 被调 1 次(INSERT reviewer.audit_history)
      5. severity 字段正确推导(critical_count > 0 → 'critical')
      6. metrics 完整
    """
    from minbook_common.agents.base import AgentInput
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()
    chapter_number = 7
    chapter_content = "Alice 终于拿到了传说中的圣剑,Merlin 惊讶地瞪大了眼睛。"

    import json
    audit_report = {
        "issues": [
            {
                "severity": "critical",
                "dimension": "character_voice",
                "description": "Merlin 的语气与 character_matrix 不一致:平时冷静的 Merlin 不应 '惊讶地瞪大眼睛'",
                "location": "para 3, sentence 2",
                "suggestion": "改为 'Merlin 微微挑眉,似乎察觉到了什么'",
            },
            {
                "severity": "minor",
                "dimension": "show_vs_tell",
                "description": "'传说中的圣剑' 是 tell,应改 show",
                "location": "para 3, sentence 1",
                "suggestion": "通过剑的细节描写暗示传说",
            },
        ],
        "overall_score": 0.82,
        "critical_count": 1,
        "major_count": 0,
        "minor_count": 1,
    }

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": json.dumps(audit_report),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 2000, "completion_tokens": 400},
                "latency_ms": 2200,
                "cost_usd": 0.025,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    from app.agents.continuity_auditor import ContinuityAuditor

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    memory = _StubMemoryClient()
    state = _StubStateClient()

    agent = ContinuityAuditor(llm, state_client=state, memory_client=memory, prompt_loader=prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "content": chapter_content,
                "chapter_number": chapter_number,
            },
        )
    )

    # 1. status + result 字段对齐
    assert output.status == "ok", f"unexpected: {output.error}"
    assert len(output.result["issues"]) == 2
    assert output.result["critical_count"] == 1
    assert output.result["minor_count"] == 1
    assert output.result["overall_score"] == 0.82
    assert output.result["issues"][0]["dimension"] == "character_voice"

    # 2. state 链路:7 个真相文件全被读
    assert state.get_calls == 7, f"expected 7 get_truth, got {state.get_calls}"
    expected_files = {
        "current_state", "character_matrix", "pending_hooks",
        "chapter_summaries", "subplot_board", "emotional_arcs", "particle_ledger",
    }
    assert set(state.file_types_seen) == expected_files

    # 3. memory pool 链路:INSERT reviewer.audit_history
    assert len(memory.pool.execute_calls) == 1
    sql, params = memory.pool.execute_calls[0]
    assert "INSERT INTO reviewer.audit_history" in sql
    assert params[0] == book_id       # $1 = book_id
    assert params[1] == chapter_number  # $2 = chapter_number
    assert params[3] == "critical"     # $4 = severity (因为 critical_count > 0)

    # 4. LLM 链路
    assert len(respx.calls) == 1

    # 5. metrics
    assert output.metrics["cost_usd"] == 0.025
    assert output.metrics["tokens"]["completion_tokens"] == 400


@pytest.mark.asyncio
@respx.mock
async def test_continuity_auditor_severity_minor(monkeypatch):
    """验证 severity 推导:无 critical/major → 'minor'。"""
    from minbook_common.agents.base import AgentInput
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    import json
    # 全是 minor → severity='minor'
    minor_report = {
        "issues": [
            {
                "severity": "minor",
                "dimension": "paragraph_flow",
                "description": "段落切换略显突兀",
                "location": "para 2 → 3",
                "suggestion": "加过渡句",
            },
        ],
        "overall_score": 0.95,
        "critical_count": 0,
        "major_count": 0,
        "minor_count": 1,
    }

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": json.dumps(minor_report),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 1500, "completion_tokens": 100},
                "latency_ms": 1500,
                "cost_usd": 0.012,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    from app.agents.continuity_auditor import ContinuityAuditor

    llm = LLMClient(service_name="agent-reviewer-service")
    prompts = PromptLoader(template_dir="prompts")
    memory = _StubMemoryClient()
    state = _StubStateClient()

    agent = ContinuityAuditor(llm, state_client=state, memory_client=memory, prompt_loader=prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"content": "短章节", "chapter_number": 1},
        )
    )

    assert output.status == "ok"
    assert output.result["critical_count"] == 0
    assert len(memory.pool.execute_calls) == 1
    sql, params = memory.pool.execute_calls[0]
    assert params[3] == "minor"  # severity 推导正确