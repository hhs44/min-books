"""错误分类器单元测试(v4 §Phase E Task 17)。"""
import asyncio

import httpx
import pytest

from app.saga.classifier import classify_error


def test_classify_network_error():
    err = httpx.ConnectError("can't connect")
    profile = classify_error(err)
    assert profile.retryable is True
    assert profile.max_attempts == 3
    assert profile.name == "transient.network"


def test_classify_429():
    response = httpx.Response(429, request=httpx.Request("GET", "http://x"))
    err = httpx.HTTPStatusError("rate limit", request=httpx.Request("GET", "http://x"), response=response)
    profile = classify_error(err)
    assert profile.retryable is True
    assert profile.name == "transient.llm_rate_limit"


def test_classify_503():
    response = httpx.Response(503, request=httpx.Request("GET", "http://x"))
    err = httpx.HTTPStatusError("overload", request=httpx.Request("GET", "http://x"), response=response)
    profile = classify_error(err)
    assert profile.retryable is True
    assert profile.name == "transient.llm_overload"


def test_classify_500():
    response = httpx.Response(500, request=httpx.Request("GET", "http://x"))
    err = httpx.HTTPStatusError("server error", request=httpx.Request("GET", "http://x"), response=response)
    profile = classify_error(err)
    assert profile.retryable is True
    assert profile.name == "transient.llm_overload"


def test_classify_4xx_permanent():
    response = httpx.Response(400, request=httpx.Request("GET", "http://x"))
    err = httpx.HTTPStatusError("bad request", request=httpx.Request("GET", "http://x"), response=response)
    profile = classify_error(err)
    assert profile.retryable is False
    assert profile.name == "permanent.llm_4xx"


def test_classify_timeout():
    err = asyncio.TimeoutError()
    profile = classify_error(err)
    assert profile.retryable is True
    assert profile.name == "transient.timeout"


def test_classify_cancelled():
    err = asyncio.CancelledError()
    profile = classify_error(err)
    assert profile.retryable is False
    assert profile.name == "cancelled"


def test_classify_unknown():
    err = ValueError("random")
    profile = classify_error(err)
    assert profile.retryable is True
    assert profile.max_attempts == 3
    assert profile.name == "unknown"
