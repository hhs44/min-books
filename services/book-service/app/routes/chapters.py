"""Chapters 列表路由(详见 v6 plan §Phase B)。

- GET /internal/books/{book_id}/chapters   列出所有章节(按 chapter_number 排序)

导入/导出在 imports.py / exports.py(独立路由文件)。
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize(row) -> dict:
    d = dict(row)
    for k in ("created_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


@router.get("/{book_id}/chapters")
async def list_chapters(
    book_id: str,
    status: Optional[str] = Query(None, description="draft | published | review"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    # 先确认 book 存在
    async with acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM shared.books WHERE id = $1", book_id)
        if not exists:
            raise HTTPException(404, f"Book {book_id} not found")
        args = [book_id]
        where = "WHERE book_id = $1"
        if status is not None:
            args.append(status)
            where += f" AND status = ${len(args)}"
        args.append(limit)
        limit_idx = len(args)
        args.append(offset)
        offset_idx = len(args)
        sql = f"""SELECT id, book_id, chapter_number, title, status, word_count,
                         version, draft_status, idempotency_key, created_at, updated_at
                  FROM shared.chapters {where}
                  ORDER BY chapter_number ASC
                  LIMIT ${limit_idx} OFFSET ${offset_idx}"""
        rows = await conn.fetch(sql, *args)
    return [_normalize(r) for r in rows]
