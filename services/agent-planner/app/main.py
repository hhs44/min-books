"""agent-planner-service:规划类 agent 服务(v3 Phase A 骨架)。

Phase A 提供:
- 完整 lifespan:init LLMClient + StateClient + MemoryClient + PromptLoader + AgentRegistrar
- /health 返 service + 注册的 agent 列表
- /internal/{service_short}/invoke 调 agent(实际 agent 在 Phase B 实现)
- 心跳向 pipeline-orchestrator 注册(v4 才有 orchestrator,目前 graceful skip)
"""
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
    memory_client = MemoryClient(service="planner", schema="planner")
    try:
        await memory_client.init()
    except Exception as e:  # noqa: BLE001
        log.warning("MemoryClient.init() failed: %s (continuing without memory)", e)
    prompt_loader = PromptLoader(template_dir="prompts")

    # Phase B:导入所有 agent 模块,触发 module-level @register_agent
    from minbook_common.agents.registry import get_global_registry
    from .agents import architect, composer, foundation_reviewer, planner  # noqa: F401,E402

    # 把全局注册表里的 agent 同步到本服务的本地 registry(供 /health 和 /internal/* 路由用)
    for agent_class in get_global_registry().all():
        agent_registry.register(agent_class)
    log.info("Registered %d agents: %s", len(agent_registry.all()),
             [a.name for a in agent_registry.all()])

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
    title="MinBook Agent Planner Service",
    version=settings.service_version,
    lifespan=lifespan,
)
instrument_fastapi(app)
app.add_middleware(InternalAuthMiddleware)

# invoke 路由:由 service_short 决定
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
