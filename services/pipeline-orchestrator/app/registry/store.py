"""Agent Registry DB 访问(orchestrator.agent_registry 表,详见 v4 §Phase A Task 4)。"""
import json
import logging

from ..db import acquire

logger = logging.getLogger(__name__)


async def upsert_agent(
    agent_id: str, service_name: str, name: str, version: str,
    card_json: dict, endpoint: str,
) -> dict:
    """注册或更新 agent(详见 v2 §4.3)。"""
    async with acquire() as conn:
        await conn.execute(
            """INSERT INTO orchestrator.agent_registry
               (agent_id, service_name, name, version, card_json, endpoint, status, last_heartbeat_at)
               VALUES ($1, $2, $3, $4, $5, $6, 'active', NOW())
               ON CONFLICT (agent_id) DO UPDATE SET
                   service_name = EXCLUDED.service_name,
                   version = EXCLUDED.version,
                   card_json = EXCLUDED.card_json,
                   endpoint = EXCLUDED.endpoint,
                   status = 'active',
                   last_heartbeat_at = NOW()""",
            agent_id, service_name, name, version, json.dumps(card_json), endpoint,
        )
    return {"agent_id": agent_id, "status": "active"}


async def heartbeat(agent_id: str) -> bool:
    """更新 last_heartbeat_at(详见 v2 §4.3)。"""
    async with acquire() as conn:
        result = await conn.execute(
            """UPDATE orchestrator.agent_registry
               SET last_heartbeat_at = NOW(), status = 'active'
               WHERE agent_id = $1""",
            agent_id,
        )
    return result.endswith(" 1") if result else False


async def find_agent(capability: str) -> dict | None:
    """按 capability 找 active agent(详见 v2 §4.4)。"""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT agent_id, service_name, endpoint, card_json
               FROM orchestrator.agent_registry
               WHERE status = 'active'
                 AND card_json->'capabilities' ? $1
               ORDER BY last_heartbeat_at DESC
               LIMIT 1""",
            capability,
        )
    if not row:
        return None
    return {
        "agent_id": row["agent_id"],
        "service_name": row["service_name"],
        "endpoint": row["endpoint"],
        "card": row["card_json"] if isinstance(row["card_json"], dict) else json.loads(row["card_json"]),
    }


async def list_agents(status: str | None = None) -> list[dict]:
    async with acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM orchestrator.agent_registry WHERE status = $1 ORDER BY service_name, name",
                status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM orchestrator.agent_registry ORDER BY service_name, name"
            )
    result = []
    for r in rows:
        d = dict(r)
        # card_json may be str (depending on driver) or dict
        if "card_json" in d and not isinstance(d["card_json"], dict):
            try:
                d["card_json"] = json.loads(d["card_json"])
            except Exception:
                pass
        result.append(d)
    return result


async def mark_stale_agents(inactive_threshold_seconds: int) -> int:
    """90s 无心跳 → inactive(详见 v2 §4.3)。"""
    async with acquire() as conn:
        result = await conn.execute(
            f"""UPDATE orchestrator.agent_registry
               SET status = 'inactive'
               WHERE status = 'active'
                 AND last_heartbeat_at < NOW() - INTERVAL '{inactive_threshold_seconds} seconds'"""
        )
    try:
        return int(result.split()[-1])
    except Exception:
        return 0
