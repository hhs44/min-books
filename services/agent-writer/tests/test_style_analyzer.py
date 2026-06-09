"""StyleAnalyzer 单元测试 — 验证 fingerprint 抽取 + writer.style_corpus 写入。

写入用 AsyncMock 替换 memory.pool.acquire() 上下文管理器,避免依赖 PG。
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import respx
from httpx import Response

from app.agents.style_analyzer import StyleAnalyzer
from minbook_common.agents.base import AgentInput


class _MockMemoryWithPool:
    """memory 桩,带可被探测的 pool.acquire() → conn.execute()。"""

    def __init__(self) -> None:
        self.conn = MagicMock()
        self.conn.execute = AsyncMock(return_value=None)
        self._cm = MagicMock()
        self._cm.__aenter__ = AsyncMock(return_value=self.conn)
        self._cm.__aexit__ = AsyncMock(return_value=None)
        self._pool = MagicMock()
        self._pool.acquire = MagicMock(return_value=self._cm)

    @property
    def pool(self):
        return self._pool

    async def recall(self, *a, **kw):
        return []

    async def store_episode(self, *a, **kw):
        return "x"


@pytest.mark.asyncio
@respx.mock
async def test_style_analyzer_writes_to_style_corpus(monkeypatch):
    """StyleAnalyzer 调 LLM → 解析 fingerprint → INSERT writer.style_corpus。"""
    from minbook_common.agents.prompt_loader import PromptLoader
    from minbook_common.clients.llm_client import LLMClient

    book_id = uuid4()

    fingerprint_json = (
        '{"avg_sentence_length": 12, "punctuation_style": "minimalist", '
        '"vocabulary_register": "literary", "pacing": "slow", '
        '"voice": "克制冷静", "signature_devices": ["留白", "象征"]}'
    )
    respx.post("http://llm-gateway:8006/internal/llm/chat").mock(
        return_value=Response(
            200,
            json={
                "content": fingerprint_json,
                "model": "gpt-4o",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 800, "completion_tokens": 80},
                "latency_ms": 900,
                "cost_usd": 0.015,
            },
        )
    )

    monkeypatch.setenv("LLM_GATEWAY_URL", "http://llm-gateway:8006")
    monkeypatch.setenv("SERVICE_SECRET", "")

    llm = LLMClient(service_name="agent-writer-service")
    prompts = PromptLoader(template_dir="prompts")
    memory = _MockMemoryWithPool()

    agent = StyleAnalyzer(llm, None, memory, prompts)

    output = await agent.run(
        AgentInput(
            book_id=book_id,
            book_settings={"sample_text": "示范样本文字。", "source": "user_uploaded"},
        )
    )

    assert output.status == "ok", output.error
    assert output.result["punctuation_style"] == "minimalist"
    assert output.result["voice"] == "克制冷静"

    # 验证写 writer.style_corpus
    memory.conn.execute.assert_awaited()  # 调过
    call_args = memory.conn.execute.await_args
    sql_text = call_args.args[0]
    assert "writer.style_corpus" in sql_text
    assert "INSERT" in sql_text
    # 参数:book_id, fingerprint_json, source
    assert call_args.args[1] == book_id
    assert call_args.args[3] == "user_uploaded"


@pytest.mark.asyncio
async def test_style_analyzer_missing_sample():
    from minbook_common.agents.prompt_loader import PromptLoader

    prompts = PromptLoader(template_dir="prompts")
    agent = StyleAnalyzer(None, None, _MockMemoryWithPool(), prompts)
    output = await agent.run(AgentInput(book_id=uuid4(), book_settings={}))
    assert output.status == "error"
    assert "sample_text" in output.error
