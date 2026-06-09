"""LLM 幂等性缓存(详见 v2 plan §11 §6.1,Redis 24h TTL)。

设计要点:
- 同一 idempotency_key + 同一 prompt 哈希 → 返回缓存
- 同一 key + 不同 prompt → 抛 IdempotencyConflict(防误用)
- 没有 key / Redis 不可用 → 不缓存(降级)
"""
import hashlib
import json
import os

import redis.asyncio as redis

from minbook_common.models import LLMChatRequest, LLMChatResponse

_redis: redis.Redis | None = None


async def init_idempotency_cache():
    global _redis
    url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    _redis = redis.from_url(url, decode_responses=True)


def _prompt_hash(req: LLMChatRequest) -> str:
    """稳定哈希:同一 (model, messages, temperature, max_tokens) 必同。"""
    payload = json.dumps(
        {
            "model": req.model,
            "messages": req.messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def get_cached(
    idempotency_key: str, request: LLMChatRequest
) -> LLMChatResponse | None:
    """如已有缓存,返回;否则 None。"""
    if not idempotency_key or _redis is None:
        return None

    raw = await _redis.get(f"llm:idem:{idempotency_key}")
    if not raw:
        return None

    data = json.loads(raw)
    if data.get("prompt_hash") != _prompt_hash(request):
        raise IdempotencyConflict(
            f"Key {idempotency_key} reused with different prompt"
        )

    return LLMChatResponse(**data["response"])


async def set_cached(
    idempotency_key: str,
    request: LLMChatRequest,
    response: LLMChatResponse,
    ttl: int = 86400,
):
    """缓存响应(默认 24h)。"""
    if not idempotency_key or _redis is None:
        return

    data = {
        "prompt_hash": _prompt_hash(request),
        "response": response.model_dump(mode="json"),
    }
    await _redis.setex(f"llm:idem:{idempotency_key}", ttl, json.dumps(data))


async def close_idempotency_cache():
    """关闭 Redis 连接(lifespan shutdown 调用)。"""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


class IdempotencyConflict(Exception):
    """同一 idempotency_key 被复用但 prompt 不一致。"""
