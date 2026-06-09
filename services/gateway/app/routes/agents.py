"""Agent 注册中心代理路由(v4 §Phase D Task 18)。

- GET  /api/agents         → 列出已注册 agents(代理到 pipeline-orchestrator)
- GET  /api/agents/{id}    → 查单个 agent card
- POST /api/agents/{id}/invoke → 触发 agent 执行(占位:v4 plan 中保留)

v4 Phase D 后接通 pipeline-orchestrator 实际端点。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("")
@router.get("/")
async def list_agents(
    status: str | None = None,
    capability: str | None = None,
    user=Depends(verify_user_token),
):
    """列出所有已注册 agent(代理到 pipeline-orchestrator)。"""
    async with SignedHTTPClient("gateway") as client:
        params = {}
        if status:
            params["status"] = status
        if capability:
            params["capability"] = capability
        r = await client.get(
            f"{settings.pipeline_orchestrator_url}/internal/orchestrator/agents",
            params=params,
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()


@router.get("/{agent_id}")
async def get_agent(agent_id: str, user=Depends(verify_user_token)):
    """查单个 agent card(代理到 pipeline-orchestrator)。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.pipeline_orchestrator_url}/internal/orchestrator/agents/{agent_id}"
        )
        if r.status_code == 404:
            raise HTTPException(404, f"Agent {agent_id} not found")
        r.raise_for_status()
        return r.json()


@router.post("/{agent_id}/invoke")
async def invoke_agent(
    agent_id: str, body: dict, user=Depends(verify_user_token)
):
    """直接 invoke agent(非完整 pipeline)— 留作 API 兼容:v4 plan 主路径走 /write/next。"""
    raise HTTPException(
        status_code=501,
        detail=(
            f"Direct agent invoke for '{agent_id}' is not the v4 main path. "
            "Use POST /api/books/{book_id}/write/next for full chapter writing pipeline."
        ),
    )
