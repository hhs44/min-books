"""Book 导出路由(详见 v6 plan §Phase B)。

- GET /internal/books/{book_id}/export?format=markdown|json|txt

  - markdown: "# {title}\n\n## 第 N 章 {chapter_title}\n\n{content}\n\n"
  - txt:      "{title}\n\n第 N 章 {chapter_title}\n\n{content}\n\n"
  - json:     完整结构化 dump
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{book_id}/export")
async def export_book(book_id: str, format: str = Query("markdown")):
    fmt = format.lower()
    if fmt not in ("markdown", "md", "json", "txt"):
        raise HTTPException(400, f"Unsupported format: {format}")

    async with acquire() as conn:
        book = await conn.fetchrow(
            """SELECT id, title, genre, language, config_json, created_at, updated_at
               FROM shared.books WHERE id = $1""",
            book_id,
        )
        if not book:
            raise HTTPException(404, f"Book {book_id} not found")
        chapters = await conn.fetch(
            """SELECT chapter_number, title, content, status, word_count
               FROM shared.chapters
               WHERE book_id = $1
               ORDER BY chapter_number ASC""",
            book_id,
        )

    book_d = dict(book)
    for k in ("created_at", "updated_at"):
        if book_d.get(k) is not None:
            book_d[k] = str(book_d[k])

    if fmt == "json":
        return JSONResponse({
            "book": book_d,
            "chapters": [dict(c) for c in chapters],
        })

    title = book_d.get("title", "Untitled")
    if fmt in ("markdown", "md"):
        out = [f"# {title}\n"]
        for c in chapters:
            out.append(f"\n## 第 {c['chapter_number']} 章 {c.get('title') or ''}\n")
            out.append(f"\n{c.get('content') or ''}\n")
        return PlainTextResponse("\n".join(out), media_type="text/markdown")
    else:  # txt
        out = [f"{title}\n", "=" * len(title) + "\n"]
        for c in chapters:
            out.append(f"\n第 {c['chapter_number']} 章 {c.get('title') or ''}\n")
            out.append("-" * 40 + "\n")
            out.append(f"\n{c.get('content') or ''}\n")
        return PlainTextResponse("\n".join(out), media_type="text/plain")
