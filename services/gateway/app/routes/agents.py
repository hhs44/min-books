"""Agent 注册中心代理路由(v3 Phase A 占位,v4 pipeline-orchestrator 实现后接通)。

- GET  /api/agents          -> 列出所有已注册 agent(pipeline-orchestrator 实现后接通)
- GET  /api/agents/{id}     -> 查单个 agent card
- POST /api/agents/{id}/invoke -> 触发 agent 执行(最终调 pipeline-orchestrator)

当前 v3 plan 阶段 pipeline-orchestrator 尚未实现,所有端点返 501 Not Implemented。
"""
from fastapi import APIRouter, Depends, HTTPException

from minbook_common.middleware import verify_user_token

router = APIRouter()


@router.get("")
@router.get("/")
async def list_agents(user=Depends(verify_user_token)) -> dict:
    """列出所有已注册 agent。v4 之前返 501。"""
    raise HTTPException(
        status_code=501,
        detail="Agent registry not yet implemented; pipeline-orchestrator is in v4 plan",
    )


@router.get("/{agent_id}")
async def get_agent(agent_id: str, user=Depends(verify_user_token)) -> dict:
    """查单个 agent card。v4 之前返 501。"""
    raise HTTPException(
        status_code=501,
        detail=f"Agent '{agent_id}' lookup not yet implemented; pipeline-orchestrator is in v4 plan",
    )


@router.post("/{agent_id}/invoke")
async def invoke_agent(agent_id: str, body: dict, user=Depends(verify_user_token)) -> dict:
    """触发 agent 执行(调 pipeline-orchestrator)。v4 之前返 501。"""
    raise HTTPException(
        status_code=501,
        detail=f"Agent '{agent_id}' invoke not yet implemented; pipeline-orchestrator is in v4 plan",
    )
