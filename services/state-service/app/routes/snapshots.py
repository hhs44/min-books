"""状态快照(详见 v2 plan §Phase C Task 20,v2 spec §11 §3.1)。

- POST /internal/state/{book_id}/snapshot  → 写一行 state.state_snapshots
- GET  /internal/state/{book_id}/snapshots → 列出最近 N 条(默认 20)
"""
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import acquire

router = APIRouter()


class SnapshotCreate(BaseModel):
    book_id: UUID
    chapter_number: int | None = None
    snapshot_json: dict[str, Any]


@router.post("/{book_id}/snapshot")
async def create_snapshot(book_id: UUID, body: SnapshotCreate):
    """创建快照(写真相前自动调用,详见 §3.1)。"""
    snapshot_json = json.dumps(body.snapshot_json)  # asyncpg → ::jsonb
    async with acquire() as conn:
        snapshot_id = await conn.fetchval(
            """INSERT INTO state.state_snapshots (book_id, chapter_number, snapshot_json)
               VALUES ($1, $2, $3::jsonb) RETURNING id""",
            body.book_id,
            body.chapter_number,
            snapshot_json,
        )
    return {"snapshot_id": str(snapshot_id)}


@router.get("/{book_id}/snapshots")
async def list_snapshots(book_id: UUID, limit: int = 20):
    """列出 book 的最近 N 条快照(默认 20,按时间倒序)。"""
    async with acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, chapter_number, created_at
               FROM state.state_snapshots
               WHERE book_id = $1
               ORDER BY created_at DESC
               LIMIT $2""",
            book_id,
            limit,
        )
    return [
        {
            "id": str(r["id"]),
            "chapter_number": r["chapter_number"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
