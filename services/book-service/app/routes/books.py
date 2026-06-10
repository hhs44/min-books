"""Books CRUD 路由(详见 v6 plan §Phase B)。

- POST   /internal/books                   创建
- GET    /internal/books                   列表(支持 ?language=&genre=&limit=&offset=)
- GET    /internal/books/{book_id}         详情
- PUT    /internal/books/{book_id}         更新(title / genre / language / config_json)
- DELETE /internal/books/{book_id}         删除(级联清 chapters / settings / daemon_configs)
"""
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..db import acquire

logger = logging.getLogger(__name__)
router = APIRouter()


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    genre: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field("zh", max_length=10)
    config_json: dict[str, Any] = Field(default_factory=dict)


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    genre: Optional[str] = Field(None, max_length=100)
    language: Optional[str] = Field(None, max_length=10)
    config_json: Optional[dict[str, Any]] = None


def _normalize(row) -> dict:
    if row is None:
        return None
    d = dict(row)
    for k in ("created_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    # config_json 是 jsonb → 已自动转 dict
    return d


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_book(req: BookCreate):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO shared.books (title, genre, language, config_json)
               VALUES ($1, $2, $3, $4::jsonb)
               RETURNING id, title, genre, language, config_json, created_at, updated_at""",
            req.title, req.genre, req.language, json.dumps(req.config_json),
        )
    return _normalize(row)


@router.get("")
async def list_books(
    language: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    clauses = []
    args = []
    if language is not None:
        args.append(language)
        clauses.append(f"language = ${len(args)}")
    if genre is not None:
        args.append(genre)
        clauses.append(f"genre = ${len(args)}")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(limit)
    limit_idx = len(args)
    args.append(offset)
    offset_idx = len(args)
    sql = f"""SELECT id, title, genre, language, config_json, created_at, updated_at
             FROM shared.books {where}
             ORDER BY created_at DESC
             LIMIT ${limit_idx} OFFSET ${offset_idx}"""
    async with acquire() as conn:
        rows = await conn.fetch(sql, *args)
    return [_normalize(r) for r in rows]


@router.get("/{book_id}")
async def get_book(book_id: str):
    async with acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, title, genre, language, config_json, created_at, updated_at
               FROM shared.books WHERE id = $1""",
            book_id,
        )
    if not row:
        raise HTTPException(404, f"Book {book_id} not found")
    return _normalize(row)


@router.put("/{book_id}")
async def update_book(book_id: str, req: BookUpdate):
    # 动态拼 SET 子句(只更新非空字段)
    sets = []
    args = []
    for field, value in req.model_dump(exclude_unset=True).items():
        if value is None and field != "config_json":
            continue
        if field == "config_json" and value is not None:
            args.append(json.dumps(value))
            sets.append(f"config_json = ${len(args)}::jsonb")
        else:
            args.append(value)
            sets.append(f"{field} = ${len(args)}")
    if not sets:
        raise HTTPException(400, "No fields to update")
    sets.append("updated_at = now()")
    args.append(book_id)
    sql = f"""UPDATE shared.books SET {', '.join(sets)}
             WHERE id = ${len(args)}
             RETURNING id, title, genre, language, config_json, created_at, updated_at"""
    async with acquire() as conn:
        row = await conn.fetchrow(sql, *args)
    if not row:
        raise HTTPException(404, f"Book {book_id} not found")
    return _normalize(row)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: str):
    async with acquire() as conn:
        result = await conn.execute("DELETE FROM shared.books WHERE id = $1", book_id)
    if "DELETE 0" in (result or ""):
        raise HTTPException(404, f"Book {book_id} not found")
    return None
