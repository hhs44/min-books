"""MinBook Gateway (Phase 6 minimal). 业务实现在 v2 plan。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi
from minbook_common.middleware import InternalAuthMiddleware

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "unknown")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8000"))


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title=f"MinBook {SERVICE_NAME}", lifespan=lifespan)
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(SERVICE_NAME, os.environ.get("SERVICE_VERSION", "0.1.0"))
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
