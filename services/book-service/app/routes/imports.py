"""Chapters 导入路由(详见 v6 plan §Phase B)。

- POST /internal/books/{book_id}/chapters/import   接受 multipart/form-data 上传文件
  - TXT:按 \\n\\n 拆章节(每段 = 1 章,首行为标题候选)
  - MD:按 ^#  拆章节
  - EPUB:暂返 501

成功后批量 INSERT shared.chapters 并返 created chapters。
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


_MD_HEADING_RE = re.compile(r"(?m)^#{1,3}\s+(.+?)\s*$")


def _split_md(text: str) -> list[tuple[str, str]]:
    """返 [(title, content), ...] 列表(空内容段会被丢弃)。"""
    parts = _MD_HEADING_RE.split(text)
    chapters = []
    # parts 是 [pre, title1, body1, title2, body2, ...]
    if parts and parts[0].strip():
        # 把 pre 当作第一章正文(无标题 → "前言" 或 第 1 章)
        chapters.append(("前言", parts[0].strip()))
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not body:
            continue
        chapters.append((title, body))
    return chapters


def _split_txt(text: str) -> list[tuple[str, str]]:
    """按 \\n\\n 拆;首行当标题(若是短文本),否则标题 = "第 N 章"。"""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chapters = []
    for i, p in enumerate(paragraphs, 1):
        lines = p.splitlines()
        # 如果首行短(< 60 字符 且 不以句号结尾) → 当标题
        if lines and len(lines[0]) <= 60 and not lines[0].endswith(("。", ".", "!", "!", "?", "?")):
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip() or p
        else:
            title = f"第 {i} 章"
            body = p
        chapters.append((title, body))
    return chapters


@router.post("/{book_id}/chapters/import", status_code=status.HTTP_201_CREATED)
async def import_chapters(
    book_id: str,
    file: UploadFile = File(...),
    format: Optional[str] = Form(None, description="txt|md|epub;若未传,从 filename 后缀推断"),
):
    # 1. 确认 book 存在
    async with acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM shared.books WHERE id = $1", book_id)
        if not exists:
            raise HTTPException(404, f"Book {book_id} not found")

    # 2. 解析 format
    fmt = (format or (file.filename.rsplit(".", 1)[-1] if file.filename else "")).lower()
    raw = (await file.read()).decode("utf-8", errors="replace")

    if fmt == "epub":
        raise HTTPException(501, "EPUB import not yet supported (v6 defer)")
    if fmt not in ("txt", "md", "markdown"):
        raise HTTPException(400, f"Unsupported format: {fmt!r}; expected txt|md|epub")

    chapters = _split_md(raw) if fmt in ("md", "markdown") else _split_txt(raw)
    if not chapters:
        raise HTTPException(400, "No chapters parsed from uploaded file")

    # 3. 批量插入
    created = []
    async with acquire() as conn:
        # 找到当前 max chapter_number,从 max+1 开始
        next_n = await conn.fetchval(
            "SELECT COALESCE(MAX(chapter_number), 0) + 1 FROM shared.chapters WHERE book_id = $1",
            book_id,
        )
        for offset, (title, body) in enumerate(chapters):
            n = next_n + offset
            row = await conn.fetchrow(
                """INSERT INTO shared.chapters
                       (book_id, chapter_number, title, content, status, word_count, version)
                   VALUES ($1, $2, $3, $4, 'published', $5, 1)
                   RETURNING id, book_id, chapter_number, title, status, word_count,
                             version, draft_status, created_at, updated_at""",
                book_id, n, title, body, len(body),
            )
            d = dict(row)
            for k in ("created_at", "updated_at"):
                if d.get(k) is not None:
                    d[k] = str(d[k])
            created.append(d)
    return {"imported": len(created), "chapters": created}
