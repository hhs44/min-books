"""Channel CRUD + test 端点(详见 v2 plan §Phase D Task 24)。

- GET  /internal/channels[?book_id=...]   列表(脱敏 config)
- POST /internal/channels                 新建
- PUT  /internal/channels/{id}            更新 config / enabled
- POST /internal/channels/{id}/test       发测试消息
- POST /internal/notify/{book_id}         触发发通知(并发 send)
"""
import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..channels import CHANNEL_REGISTRY, NotificationPayload
from ..db import acquire

router = APIRouter()


class ChannelCreate(BaseModel):
    book_id: UUID
    channel_type: str
    config_json: dict
    enabled: bool = True


def _summarize(channel_type: str, config: dict) -> dict:
    """脱敏 config(可能含 token/secret)。"""
    if not isinstance(config, dict):
        return {}
    if channel_type == "telegram":
        return {"chat_id": (str(config.get("chat_id", ""))[:4] + "***")}
    if channel_type in ("feishu", "wechat_work"):
        return {"webhook_url": (str(config.get("webhook_url", ""))[:30] + "...")}
    if channel_type == "webhook":
        return {"url": (str(config.get("url", ""))[:30] + "...")}
    return {}


def _coerce_config(raw) -> dict:
    """asyncpg 对 jsonb 列有时返回 str,有时返回 dict,统一处理。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return {}


@router.get("/channels")
async def list_channels(book_id: UUID | None = None):
    async with acquire() as conn:
        if book_id:
            rows = await conn.fetch(
                "SELECT id, book_id, channel_type, config_json, enabled "
                "FROM notification.notification_channels WHERE book_id = $1",
                book_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, book_id, channel_type, config_json, enabled "
                "FROM notification.notification_channels"
            )
    return [
        {
            "id": str(r["id"]),
            "book_id": str(r["book_id"]),
            "channel_type": r["channel_type"],
            "config_summary": _summarize(r["channel_type"], _coerce_config(r["config_json"])),
            "enabled": r["enabled"],
        }
        for r in rows
    ]


@router.post("/channels")
async def create_channel(body: ChannelCreate):
    if body.channel_type not in CHANNEL_REGISTRY:
        raise HTTPException(400, f"Invalid channel_type: {body.channel_type}")

    async with acquire() as conn:
        channel_id = await conn.fetchval(
            """INSERT INTO notification.notification_channels
               (book_id, channel_type, config_json, enabled)
               VALUES ($1, $2, $3::jsonb, $4) RETURNING id""",
            body.book_id,
            body.channel_type,
            json.dumps(body.config_json),
            body.enabled,
        )
    return {"id": str(channel_id)}


@router.put("/channels/{channel_id}")
async def update_channel(channel_id: UUID, body: dict):
    config_json = body.get("config_json")
    enabled = body.get("enabled", True)

    async with acquire() as conn:
        if config_json is not None:
            await conn.execute(
                """UPDATE notification.notification_channels
                   SET config_json = $1::jsonb, enabled = $2
                   WHERE id = $3""",
                json.dumps(config_json),
                enabled,
                channel_id,
            )
        else:
            await conn.execute(
                """UPDATE notification.notification_channels
                   SET enabled = $1
                   WHERE id = $2""",
                enabled,
                channel_id,
            )
    return {"status": "ok"}


@router.post("/channels/{channel_id}/test")
async def test_channel(channel_id: UUID):
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT channel_type, config_json FROM notification.notification_channels WHERE id = $1",
            channel_id,
        )
    if not row:
        raise HTTPException(404, "Channel not found")

    channel_class = CHANNEL_REGISTRY.get(row["channel_type"])
    if not channel_class:
        raise HTTPException(400, f"Unknown channel_type: {row['channel_type']}")

    config = _coerce_config(row["config_json"])
    try:
        ok = await channel_class(config).test()
    except Exception as e:
        return {"status": "failed", "error": f"{type(e).__name__}: {e}"}
    return {"status": "ok" if ok else "failed"}


@router.post("/notify/{book_id}")
async def notify(book_id: UUID, body: dict):
    """并发 send 到该 book 所有 enabled channels。"""
    payload = NotificationPayload(**body)
    payload.book_id = str(book_id)

    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, channel_type, config_json FROM notification.notification_channels
               WHERE book_id = $1 AND enabled = true""",
            book_id,
        )

    async def _send_one(row) -> dict:
        config = _coerce_config(row["config_json"])
        channel_class = CHANNEL_REGISTRY.get(row["channel_type"])
        if not channel_class:
            return {"channel": row["channel_type"], "ok": False, "error": "unknown channel_type"}
        try:
            ok = await channel_class(config).send(payload)
            return {"channel": row["channel_type"], "ok": ok}
        except Exception as e:
            return {
                "channel": row["channel_type"],
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            }

    results = await asyncio.gather(*[_send_one(r) for r in rows], return_exceptions=False)
    return results
