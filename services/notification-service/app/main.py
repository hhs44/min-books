"""Notification Service:多渠道告警 + NATS 事件订阅(详见 v2 plan §Phase D)。

Lifespan:
  - init DB pool (asyncpg, svc_notify 用户)
  - connect NATS
  - start consumer (alert.* + chapter.failed)
  - on shutdown: cancel consumer + close NATS + close DB
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.middleware import InternalAuthMiddleware
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi
from minbook_common.nats_client import MinBookNATS

from .config import get_settings
from .consumer import start_consumer
from .db import close_db, init_db
from .routes import channels

settings = get_settings()
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(settings.service_name, settings.service_version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. DB
    await init_db()
    # 2. NATS
    nats = MinBookNATS(
        url=os.environ.get("NATS_URL", "nats://nats:4222"),
        service_name=settings.service_name,
        service_version=settings.service_version,
    )
    await nats.connect()
    # 3. Start consumer (in background)
    consumer_task = asyncio.create_task(start_consumer(nats))
    try:
        yield
    finally:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        await nats.close()
        await close_db()


app = FastAPI(
    title="MinBook Notification Service",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)

# 路由
app.include_router(channels.router, prefix="/internal", tags=["channels"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", "8000")))
