"""agent invoke 端点:Pipeline Orchestrator 调这个端点跑某个 agent。

- POST /internal/{service_short}/invoke
- 接收 InvokeRequest(agent_name + input dict)
- 用 registry 实例化 agent → run → 返回 AgentOutput
- v3 Phase A:仅做骨架,真正 agent 在 Phase B/C/D 实现
"""
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from minbook_common.agents.base import AgentInput

log = logging.getLogger(__name__)
router = APIRouter()


class InvokeRequest(BaseModel):
    agent_name: str
    input: dict[str, Any]


@router.post("/invoke")
async def invoke(req: InvokeRequest) -> dict[str, Any]:
    """Pipeline Orchestrator 调这个跑一个 agent。

    依赖 main.py 暴露的全局单例(llm_client / state_client / memory_client / prompt_loader / registry)。
    """
    # 延迟 import 避免循环引用
    from .. import main as app_main

    registry = app_main.agent_registry
    agent_class = registry.get(req.agent_name)
    if not agent_class:
        raise HTTPException(404, f"Agent {req.agent_name} not found in this service")

    if not all([
        app_main.llm_client, app_main.state_client,
        app_main.memory_client, app_main.prompt_loader,
    ]):
        raise HTTPException(503, "Service not fully initialized")

    agent = agent_class(
        llm_client=app_main.llm_client,
        state_client=app_main.state_client,
        memory_client=app_main.memory_client,
        prompt_loader=app_main.prompt_loader,
    )

    try:
        agent_input = AgentInput(**req.input)
    except Exception as e:
        raise HTTPException(400, f"Invalid input: {e}") from e

    try:
        output = await agent.run(agent_input)
        return output.model_dump(mode="json")
    except Exception as e:
        log.exception("agent %s run failed", req.agent_name)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
        }
