"""API Gateway:对外 /api/* 入口(详见 v2 plan §Phase A + Phase C)。

- 鉴权(InternalAuthMiddleware 来自 minbook-common,只验 /internal/*)
- 限流(rate_limit 中间件,Redis 滑动窗口)
- i18n(从 Accept-Language 解析 locale)
- 路由(9 组:auth/books/llm/config/cost/doctor/notifications/state/style/write_proxy)
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.config import get_settings as get_common_settings
from minbook_common.middleware import InternalAuthMiddleware
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi

from .config import get_settings
from .middleware.i18n import I18nMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routes import (
    agents,
    auth,
    books,
    config,
    cost,
    doctor,
    llm,
    notifications,
    state,
    style,
    write_proxy,
)

settings = get_settings()
common = get_common_settings()

setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(settings.service_name, settings.service_version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动 banner + 自动生成本地 JWT token
    from minbook_common.auth import init_local_token

    if common.jwt_secret:
        expiry = int(os.environ.get("JWT_EXPIRY_SECONDS", str(365 * 24 * 3600)))
        token = init_local_token(common.jwt_secret, expiry)
        print(
            f"""
╔══════════════════════════════════════════════════════════════╗
║  MinBook Gateway started on http://localhost:8000            ║
║  Auth token (first run): {token[:50]}...
║  Token saved at: ~/.minbook/auth.token                       ║
╚══════════════════════════════════════════════════════════════╝
""",
            file=sys.stderr,
        )
    yield


app = FastAPI(
    title="MinBook Gateway",
    version=settings.service_version,
    lifespan=lifespan,
)

# 中间件顺序:tracing -> i18n -> rate limit -> internal auth
instrument_fastapi(app)
app.add_middleware(
    I18nMiddleware,
    default_locale=settings.default_locale,
    supported=settings.supported_locales,
)
app.add_middleware(
    RateLimitMiddleware,
    redis_url=common.redis_url,
    per_minute=settings.rate_limit_per_minute,
)
app.add_middleware(InternalAuthMiddleware)

# 路由(9 组,10 个 include_router 调用 —— style / write_proxy / state 共享 /api/books 前缀)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(cost.router, prefix="/api/cost", tags=["cost"])
app.include_router(doctor.router, prefix="/api/doctor", tags=["doctor"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(style.router, prefix="/api/books", tags=["style"])
app.include_router(write_proxy.router, prefix="/api/books", tags=["write"])
app.include_router(state.router, prefix="/api/books", tags=["state"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name, "version": settings.service_version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", "8000")))
