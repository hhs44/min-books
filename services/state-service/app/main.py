"""State Service:7 真相文件 + 快照 + 共享知识(详见 v2 plan §Phase C)。

Lifespan:
  - init DB pool (asyncpg, svc_state 用户)
  - on shutdown: close pool

Routes:
  - /internal/state/{book_id}/truth/{file_type}    GET / PUT(乐观并发)
  - /internal/state/{book_id}/snapshot             POST(创建快照)
  - /internal/state/{book_id}/snapshots            GET(列出最近 20)
  - /internal/state/{book_id}/memory               GET(501 v3 defer)
  - /internal/config                                GET / PUT(共享全局配置)
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.middleware import InternalAuthMiddleware
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi

from .config import get_settings
from .db import close_db, init_db
from .routes import config, memory, snapshots, truth

settings = get_settings()
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(settings.service_name, settings.service_version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        yield
    finally:
        await close_db()


app = FastAPI(
    title="MinBook State Service",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)

# 路由
app.include_router(truth.router, prefix="/internal/state", tags=["truth"])
app.include_router(snapshots.router, prefix="/internal/state", tags=["snapshots"])
app.include_router(memory.router, prefix="/internal/state", tags=["memory"])
app.include_router(config.router, prefix="/internal", tags=["config"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name, "version": settings.service_version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", "8000")))
