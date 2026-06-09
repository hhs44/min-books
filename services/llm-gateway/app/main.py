"""LLM Gateway:多服务商适配 + 成本计量(详见 v2 plan §Phase B)。

Lifespan:
  - init idempotency cache (Redis)
  - init DB pool (asyncpg)
  - on shutdown: close both

Routes:
  - POST /internal/llm/chat
  - GET  /internal/llm/providers
  - GET  /internal/llm/models
  - POST /internal/llm/test
  - GET  /api/cost/{summary,daily,by-book,recent-calls}
  - PUT  /api/cost/thresholds
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.middleware import InternalAuthMiddleware
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi

from .cache import close_idempotency_cache, init_idempotency_cache
from .config import get_settings
from .db import close_db, init_db
from .routes import chat, cost, providers

settings = get_settings()
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(settings.service_name, settings.service_version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_idempotency_cache()
    await init_db()
    try:
        yield
    finally:
        await close_idempotency_cache()
        await close_db()


app = FastAPI(
    title="MinBook LLM Gateway",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)

# 路由
app.include_router(chat.router, prefix="/internal/llm", tags=["chat"])
app.include_router(providers.router, prefix="/internal/llm", tags=["providers"])
app.include_router(cost.router, prefix="/api/cost", tags=["cost"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name, "version": settings.service_version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", "8000")))
