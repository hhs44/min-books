"""agent-writer-service e2e invoke 测试(Phase E Task 2)。

模拟完整 invoke 链路:invoke → prompt render → LLM call (respx mock) →
parse JSON → 写 writer.style_corpus (memory pool) → return AgentOutput。

测试覆盖:StyleAnalyzer(写 writer.style_corpus)— 7 agents 中
唯一写 memory DB 的(其他 6 个都是纯 LLM 或纯逻辑)。
"""
from uuid import uuid4

import pytest
import respx
from httpx import Response


class _StubMemoryPool:
    """模拟 MemoryClient._pool:跟踪 execute 调用,记录 INSERT 内容。"""

    def __init__(self):
        self.execute_calls = []
        self.acquire_count = 0

    def acquire(self):
        """支持 async with:返 self,且 mock __aenter__/__aexit__。"""
        return _AcquireCtx(self)

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"


class _AcquireCtx:
    """async with 桩。"""

    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        self.pool.acquire_count += 1
        return self.pool

    async def __aexit__(self, *a):
        return False


class _StubMemoryClient:
    """memory client 桩:暴露 .pool 属性(真实 asyncpg.Pool 替代物)。"""

    def __init__(self):
        self.pool = _StubMemoryPool()
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


@pytest.mark.asyncio
@respx.mock
async def test_style_analyzer_e2e_writes_style_corpus(monkeypatch):
    """StyleAnalyzer 完整链路:LLM 抽指纹 → 解析 JSON → INSERT writer.style_corpus。

    验证 5 件事:
      1. LLM Gateway 被调 1 次
      2. 返回 fingerprint JSON 含 sentence_length / punctuation / rhythm
      3. memory.pool.execute 被调 1 次(INSERT)
      4. INSERT 的 SQL 含 writer.style_corpus + 参数含正确 fingerprint
      5. metrics 完整
    """
    from minbook_common.agents.base import AgentInput
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()
    sample_text = "魔法学院的大门在夕阳下泛着金光。Alice 紧张地攥着入学信。"

    import json
    fingerprint = {
        "sentence_length": {"avg": 18, "max": 35, "min": 8},
        "punctuation": {"period_ratio": 0.7, "exclamation_ratio": 0.05, "question_ratio": 0.1},
        "vocabulary": {"level": "literary", "preferred_words": ["光芒", "寂静", "远方"]},
        "rhythm": {"tempo": "medium", "paragraph_length": 3},
        "metaphor_density": 0.15,
    }

    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": json.dumps(fingerprint),
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 600, "completion_tokens": 300},
                "latency_ms": 800,
                "cost_usd": 0.008,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    from app.agents.style_analyzer import StyleAnalyzer

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    memory = _StubMemoryClient()

    agent = StyleAnalyzer(llm, state_client=None, memory_client=memory, prompt_loader=prompts)
    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={
                "sample_text": sample_text,
                "source": "chapter_1",
            },
        )
    )

    # 1. status + result 字段对齐
    assert output.status == "ok", f"unexpected: {output.error}"
    assert output.result["sentence_length"]["avg"] == 18
    assert output.result["punctuation"]["period_ratio"] == 0.7
    assert output.result["vocabulary"]["level"] == "literary"
    assert output.result["metaphor_density"] == 0.15

    # 2. memory.pool.execute 被调 1 次(INSERT writer.style_corpus)
    assert len(memory.pool.execute_calls) == 1, (
        f"expected 1 execute call, got {len(memory.pool.execute_calls)}"
    )
    sql, params = memory.pool.execute_calls[0]
    assert "INSERT INTO writer.style_corpus" in sql
    assert params[0] == book_id  # $1 = book_id
    assert "sentence_length" in params[1]  # $2 = fingerprint JSON str

    # 3. acquire context manager 被用
    assert memory.pool.acquire_count == 1

    # 4. LLM 链路
    assert len(respx.calls) == 1

    # 5. metrics
    assert output.metrics["cost_usd"] == 0.008
    assert output.metrics["tokens"]["completion_tokens"] == 300


@pytest.mark.asyncio
async def test_style_analyzer_missing_sample_returns_error(monkeypatch):
    """缺 sample_text → status=error,不入 LLM,不写 DB。

    边界测试:验证参数缺失时降级行为。
    """
    from minbook_common.agents.base import AgentInput
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    from app.agents.style_analyzer import StyleAnalyzer

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    memory = _StubMemoryClient()

    agent = StyleAnalyzer(llm, state_client=None, memory_client=memory, prompt_loader=prompts)
    output = await agent.run(
        AgentInput(book_id=uuid4(), book_settings={})  # 无 sample_text
    )

    assert output.status == "error"
    assert "missing 'sample_text'" in (output.error or "")
    assert len(memory.pool.execute_calls) == 0  # DB 不写