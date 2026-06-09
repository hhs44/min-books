"""7 真相文件 CRUD(详见 v2 plan §Phase C Task 19,v2 spec §2.6)。

- GET /internal/state/{book_id}/truth/{file_type}
- PUT /internal/state/{book_id}/truth/{file_type}
    乐观并发:body.expected_version 必须匹配 DB 当前 version,否则 409
    UPSERT 用 ON CONFLICT DO UPDATE 自动 +1 version
"""
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import acquire

router = APIRouter()

VALID_FILE_TYPES = {
    "current_state",
    "character_matrix",
    "pending_hooks",
    "chapter_summaries",
    "subplot_board",
    "emotional_arcs",
    "particle_ledger",
}


@router.get("/{book_id}/truth/{file_type}")
async def get_truth(book_id: UUID, file_type: str):
    """读真相文件。不存在返 {content: {}, version: 0}。"""
    if file_type not in VALID_FILE_TYPES:
        raise HTTPException(400, f"Invalid file_type, must be one of {sorted(VALID_FILE_TYPES)}")
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, version FROM state.truth_files WHERE book_id = $1 AND file_type = $2",
            book_id,
            file_type,
        )
    if not row:
        return {"content": {}, "version": 0}
    content = row["content"]
    # asyncpg 把 jsonb 解码成 str(默认 codec);还原成 dict
    if isinstance(content, str):
        content = json.loads(content)
    return {"content": content, "version": row["version"]}


class TruthUpdate(BaseModel):
    content: dict[str, Any]
    expected_version: int | None = None  # None = 强制覆盖;int = 乐观并发校验


@router.put("/{book_id}/truth/{file_type}")
async def update_truth(book_id: UUID, file_type: str, body: TruthUpdate):
    """写真相文件(乐观并发)。

    - expected_version=None: 直接覆盖(用于初始化或迁移场景)
    - expected_version=int: DB 当前 version 必须 == expected_version,否则 409
    - UPSERT 语义:不存在插入(version=1);存在则 version+1
    """
    if file_type not in VALID_FILE_TYPES:
        raise HTTPException(400, f"Invalid file_type, must be one of {sorted(VALID_FILE_TYPES)}")

    content_json = json.dumps(body.content)  # asyncpg 需 str → ::jsonb

    async with acquire() as conn:
        async with conn.transaction():
            if body.expected_version is not None:
                current = await conn.fetchval(
                    "SELECT version FROM state.truth_files WHERE book_id = $1 AND file_type = $2 FOR UPDATE",
                    book_id,
                    file_type,
                )
                if current is not None and current != body.expected_version:
                    raise HTTPException(
                        409,
                        f"Version conflict: expected {body.expected_version}, got {current}",
                    )

            new_version = await conn.fetchval(
                """INSERT INTO state.truth_files (book_id, file_type, content, version, updated_at)
                   VALUES ($1, $2, $3::jsonb, 1, NOW())
                   ON CONFLICT (book_id, file_type)
                   DO UPDATE SET content = $3::jsonb,
                                 version = state.truth_files.version + 1,
                                 updated_at = NOW()
                   RETURNING version""",
                book_id,
                file_type,
                content_json,
            )
    return {"status": "ok", "version": new_version}
