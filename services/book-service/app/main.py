"""Book Service: 真实实现(详见 v6 plan §Phase B)。

Lifespan:
  - init DB pool (asyncpg, svc_book 用户)
  - on shutdown: close pool

Routes:
  - /internal/books                              POST / GET
  - /internal/books/{book_id}                    GET / PUT / DELETE
  - /internal/books/{book_id}/chapters           GET
  - /internal/books/{book_id}/chapters/import    POST (TXT/MD 解析;EPUB 暂返 501)
  - /internal/books/{book_id}/export             GET (markdown / json / txt)
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.middleware import InternalAuthMiddleware
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi

from .config import get_settings
from .db import close_db, init_db
from .routes import books as books_route
from .routes import chapters as chapters_route
from .routes import exports as exports_route
from .routes import imports as imports_route

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
    title="MinBook Book Service",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)

# 路由
app.include_router(books_route.router, prefix="/internal/books", tags=["books"])
# chapters / import / export 用子路由(共享 {book_id} 段)
app.include_router(chapters_route.router, prefix="/internal/books", tags=["chapters"])
app.include_router(imports_route.router, prefix="/internal/books", tags=["imports"])
app.include_router(exports_route.router, prefix="/internal/books", tags=["exports"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name, "version": settings.service_version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", settings.service_port)))
