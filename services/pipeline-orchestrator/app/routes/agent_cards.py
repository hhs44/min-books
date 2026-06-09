"""Agent Card 详情 / drain / DELETE 端点(v4 §Phase D Task 12)。

- GET    /internal/orchestrator/agents/{agent_id}     → 完整 card
- POST   /internal/orchestrator/agents/{agent_id}/drain → 标 'drained'
- DELETE /internal/orchestrator/agents/{agent_id}     → 删除
"""
import json
import logging

from fastapi import APIRouter, HTTPException

from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


@router.get("/{agent_id}")
async def get_card(agent_id: str):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT agent_id, service_name, name, version, card_json,
                      endpoint, status, last_heartbeat_at, registered_at, updated_at
               FROM orchestrator.agent_registry WHERE agent_id = $1""",
            agent_id,
        )
    if not row:
        raise HTTPException(404, f"Agent {agent_id} not found")
    d = dict(row)
    d["card_json"] = _normalize(d.get("card_json"))
    d["agent_id"] = d.pop("agent_id")
    d["service_name"] = d.pop("service_name")
    # 时间字段转 ISO str
    for k in ("last_heartbeat_at", "registered_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


@router.post("/{agent_id}/drain")
async def drain(agent_id: str):
    """优雅关闭标记:标 'drained',registry 不再分发新 invoke。"""
    async with acquire() as conn:
        result = await conn.execute(
            "UPDATE orchestrator.agent_registry SET status = 'drained' WHERE agent_id = $1",
            agent_id,
        )
    if "UPDATE 0" in (result or ""):
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"status": "drained", "agent_id": agent_id}


@router.delete("/{agent_id}")
async def unregister(agent_id: str):
    async with acquire() as conn:
        result = await conn.execute(
            "DELETE FROM orchestrator.agent_registry WHERE agent_id = $1",
            agent_id,
        )
    if "DELETE 0" in (result or ""):
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"status": "deleted", "agent_id": agent_id}
