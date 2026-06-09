"""Agent Registry 端点(v4 §Phase D Task 11,被 v3 启动时调)。

- POST /internal/orchestrator/agents/register              → 注册或更新
- POST /internal/orchestrator/agents/{id}/heartbeat        → 更新心跳
- GET  /internal/orchestrator/agents?status=&capability=   → 列表(支持 capability 查单个最佳匹配)
"""
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..registry.store import (
    find_agent,
    heartbeat as registry_heartbeat,
    list_agents,
    upsert_agent,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    card: dict[str, Any]
    endpoint: str


@router.post("/register")
async def register(req: RegisterRequest):
    """注册或更新 agent(详见 v2 §4.3)。"""
    card = req.card
    # 必要的字段校验
    required = ("agent_id", "service", "name", "version")
    missing = [k for k in required if not card.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required card fields: {missing}")

    result = await upsert_agent(
        agent_id=card["agent_id"],
        service_name=card["service"],
        name=card["name"],
        version=card["version"],
        card_json=card,
        endpoint=req.endpoint,
    )
    logger.info(f"Registered agent {card['agent_id']} ({card['service']}.{card['name']})")
    return result


@router.post("/{agent_id}/heartbeat")
async def heartbeat_endpoint(agent_id: str):
    success = await registry_heartbeat(agent_id)
    if not success:
        # 找不到 → 自动 upsert?设计选择:严格模式返 404
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not registered")
    return {"status": "ok", "agent_id": agent_id}


@router.get("")
async def list_endpoint(
    status: Optional[str] = Query(None, description="active | inactive | drained"),
    capability: Optional[str] = Query(None, description="按 capability 找最佳匹配 agent"),
):
    if capability:
        agent = await find_agent(capability)
        return [agent] if agent else []
    return await list_agents(status)
