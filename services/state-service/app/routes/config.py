"""全局配置(shared.global_config,详见 v2 plan §Phase C Task 21,v2 spec §12 §3.1)。

- GET  /internal/config  → 全表 {key: value}
- PUT  /internal/config  → 更新指定 key
"""
import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import acquire

router = APIRouter()


class ConfigUpdate(BaseModel):
    config_key: str
    config_value: Any  # dict / list / str / num / bool 都接受


@router.get("/config")
async def get_all_config():
    """读全局配置全表。"""
    async with acquire() as conn:
        rows = await conn.fetch("SELECT config_key, config_value FROM shared.global_config")
    return {r["config_key"]: r["config_value"] for r in rows}


@router.put("/config")
async def update_config(body: ConfigUpdate):
    """更新指定 key 的 config_value。"""
    async with acquire() as conn:
        result = await conn.execute(
            """UPDATE shared.global_config
               SET config_value = $1::jsonb, updated_at = NOW()
               WHERE config_key = $2""",
            json.dumps(body.config_value),
            body.config_key,
        )
    # asyncpg 的 execute 返回 'UPDATE N' 格式
    updated = int(result.split()[-1]) if result.startswith("UPDATE") else 0
    if updated == 0:
        return {"status": "not_found", "config_key": body.config_key}
    return {"status": "ok"}
