"""错误分类(详见 v4 §Phase B Task 7 + v2 spec §11 §1)。

分类原则:
- transient:重试(3 次 + 指数退避)
- permanent:不重试,直接 failed
- cancelled:不重试(executor 主动取消)
- unknown:重试 3 次(兜底)
"""
import asyncio
from dataclasses import dataclass
from typing import Callable

import httpx


@dataclass
class ErrorProfile:
    name: str
    retryable: bool
    max_attempts: int
    backoff_fn: Callable | None  # (attempt) -> seconds


# 缺省 profile(未知错误)
UNKNOWN_PROFILE = ErrorProfile("unknown", True, 3, lambda a: 2 ** a)


def _exp_backoff(attempt: int) -> float:
    """2^attempt + jitter(详见 §11 §1)。"""
    import random
    return 2 ** attempt + random.uniform(0, 0.2 * 2 ** attempt)


def classify_error(e: Exception) -> ErrorProfile:
    """根据异常类型 / HTTP 状态码,返回 ErrorProfile。"""
    # 1. httpx 网络层错误
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        return ErrorProfile("transient.network", True, 3, _exp_backoff)
    if isinstance(e, httpx.TimeoutException):
        return ErrorProfile("transient.timeout", True, 3, _exp_backoff)
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code if e.response else 0
        if code == 429:
            return ErrorProfile("transient.llm_rate_limit", True, 3, _exp_backoff)
        if code in (502, 503, 504):
            return ErrorProfile("transient.llm_overload", True, 3, _exp_backoff)
        if code in (408,):  # Request Timeout
            return ErrorProfile("transient.timeout", True, 3, _exp_backoff)
        if 400 <= code < 500:
            return ErrorProfile("permanent.llm_4xx", False, 0, None)
        if code >= 500:
            return ErrorProfile("transient.llm_overload", True, 3, _exp_backoff)
    # 2. asyncio 错误
    if isinstance(e, asyncio.TimeoutError):
        return ErrorProfile("transient.timeout", True, 3, _exp_backoff)
    if isinstance(e, asyncio.CancelledError):
        return ErrorProfile("cancelled", False, 0, None)
    # 3. 兜底
    return UNKNOWN_PROFILE
