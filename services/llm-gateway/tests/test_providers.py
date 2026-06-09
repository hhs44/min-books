"""LLM provider 单元测试(respx mock OpenAI 兼容协议)。"""
import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from minbook_common.models import LLMChatRequest, LLMChatResponse

from app.providers.openai_compat import OpenAICompatProvider
from app.providers.registry import get_provider


@pytest.fixture
def openai_provider():
    return OpenAICompatProvider(
        name="openai",
        default_base="https://api.openai.com/v1",
        api_key="test-key",
    )


@pytest.mark.asyncio
async def test_registry_returns_openai_compat_for_5_providers():
    for name in ["openai", "deepseek", "zhipu", "moonshot", "qwen"]:
        p = get_provider(name)
        assert isinstance(p, OpenAICompatProvider)
        assert p.name == name


def test_registry_returns_anthropic():
    p = get_provider("anthropic")
    assert p.name == "anthropic"


def test_registry_returns_ollama_subclass():
    p = get_provider("ollama")
    assert isinstance(p, OpenAICompatProvider)
    assert p.name == "ollama"
    assert p.api_key == "ollama"  # placeholder
    assert "host.docker.internal" in p.base_url or "ollama" in p.base_url


def test_registry_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("nonsense")


@pytest.mark.asyncio
async def test_estimate_cost_uses_db(monkeypatch):
    """estimate_cost should call db.fetch_provider_cost with right args."""
    p = OpenAICompatProvider(
        name="openai",
        default_base="https://api.openai.com/v1",
        api_key="test",
    )
    fake = AsyncMock(return_value=Decimal("0.0015"))
    # estimate_cost does `from ..db import fetch_provider_cost` lazily; patch at app.db
    with patch("app.db.fetch_provider_cost", fake):
        result = await p.estimate_cost(1000, 500, "gpt-4o-mini")
    assert result == Decimal("0.0015")
    fake.assert_awaited_once_with("openai", "gpt-4o-mini", 1000, 500)


@pytest.mark.asyncio
@respx.mock
async def test_chat_calls_openai_and_returns_response(openai_provider):
    """End-to-end: OpenAICompatProvider.chat() goes through openai SDK."""
    # Build a mock response that mimics openai SDK's pydantic-style object
    choice = type(
        "Choice",
        (),
        {
            "finish_reason": "stop",
            "message": type(
                "Msg", (), {"role": "assistant", "content": "ok"}
            )(),
        },
    )()
    response_obj = type(
        "Resp",
        (),
        {
            "model": "gpt-4o-mini",
            "choices": [choice],
            "usage": type("U", (), {"prompt_tokens": 5, "completion_tokens": 1})(),
        },
    )()

    mock_create = AsyncMock(return_value=response_obj)
    fake_client = type(
        "C",
        (),
        {
            "chat": type(
                "CC",
                (),
                {
                    "completions": type(
                        "CCC", (), {"create": mock_create}
                    )()
                },
            )()
        },
    )()

    with patch.object(openai_provider, "_get_client", return_value=fake_client), \
         patch.object(openai_provider, "estimate_cost", return_value=Decimal("0.0001")):
        req = LLMChatRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
        resp = await openai_provider.chat(req)

    assert resp.content == "ok"
    assert resp.usage["prompt_tokens"] == 5
    assert resp.usage["completion_tokens"] == 1
    mock_create.assert_awaited_once()


def test_prompt_hash_stable():
    from app.cache import _prompt_hash

    r1 = LLMChatRequest(
        model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
    )
    r2 = LLMChatRequest(
        model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
    )
    assert _prompt_hash(r1) == _prompt_hash(r2)
    r3 = LLMChatRequest(
        model="gpt-4o-mini", messages=[{"role": "user", "content": "bye"}]
    )
    assert _prompt_hash(r1) != _prompt_hash(r3)
