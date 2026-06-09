"""agent-reviewer-service:审核类 agent 服务(v3 Phase A 骨架)。"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minbook_common.agents.prompt_loader import PromptLoader
from minbook_common.agents.registry import AgentRegistry
from minbook_common.agents.registration import AgentRegistrar
from minbook_common.clients.llm_client import LLMClient
from minbook_common.clients.memory_client import MemoryClient
from minbook_common.clients.state_client import StateClient
from minbook_common.middleware import InternalAuthMiddleware
from minbook_otel.logging import setup_logging
from minbook_otel.tracing import init_tracing, instrument_fastapi

from .config import get_settings
from .routes import invoke as invoke_route

log = logging.getLogger(__name__)
settings = get_settings()
setup_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
init_tracing(settings.service_name, settings.service_version)


# 全局共享资源(在 lifespan 初始化)
llm_client: LLMClient | None = None
state_client: StateClient | None = None
memory_client: MemoryClient | None = None
prompt_loader: PromptLoader | None = None
agent_registry = AgentRegistry()
registrar: AgentRegistrar | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client, state_client, memory_client, prompt_loader, registrar

    llm_client = LLMClient(service_name=settings.service_name)
    state_client = StateClient(service_name=settings.service_name)
    memory_client = MemoryClient(service="reviewer", schema="reviewer")
    try:
        await memory_client.init()
    except Exception as e:  # noqa: BLE001
        log.warning("MemoryClient.init() failed: %s (continuing without memory)", e)
    prompt_loader = PromptLoader(template_dir="prompts")

    registrar = AgentRegistrar(
        service_name=settings.service_name,
        service_endpoint=f"http://{settings.service_name}:{settings.service_port}",
        heartbeat_interval=30,
    )
    try:
        registrar.start(agent_registry)
    except Exception as e:  # noqa: BLE001
        log.warning("AgentRegistrar.start() failed: %s", e)

    yield

    if registrar:
        try:
            await registrar.stop()
        except Exception:  # noqa: BLE001
            pass
    if llm_client:
        try:
            await llm_client.close()
        except Exception:  # noqa: BLE001
            pass
    if state_client:
        try:
            await state_client.close()
        except Exception:  # noqa: BLE001
            pass
    if memory_client:
        try:
            await memory_client.close()
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(
    title="MinBook Agent Reviewer Service",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)

app.include_router(
    invoke_route.router,
    prefix=f"/internal/{settings.service_short}",
    tags=["invoke"],
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "agents": [a.name for a in agent_registry.all()],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SERVICE_PORT", settings.service_port)))
