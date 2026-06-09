"""基于 Redis 的滑动窗口限流(简化版 token bucket,详见 v2 plan §Phase A Task 3)。

- 默认 60 req/min/IP(可通过环境变量覆盖)
- 跳过 /health 和 /
- 限流失败不阻塞主流程(降级放行)
- 429 返 `{"error": "rate_limit_exceeded", "limit": N}`
"""
import time

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str, per_minute: int = 60):
        super().__init__(app)
        self.redis_url = redis_url
        self.per_minute = per_minute
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if not self._redis:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def dispatch(self, request, call_next):
        # 跳过 health 和根路径
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket = int(time.time() // 60)  # 1 分钟一个 bucket
        key = f"ratelimit:{client_ip}:{bucket}"

        try:
            r = await self._get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 120)  # 2 分钟后过期

            if count > self.per_minute:
                return JSONResponse(
                    {"error": "rate_limit_exceeded", "limit": self.per_minute},
                    status_code=429,
                )
        except Exception:
            # 限流失败不阻塞主流程
            pass

        return await call_next(request)
