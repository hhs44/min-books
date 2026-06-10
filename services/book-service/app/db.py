"""book-service 专用 DB 连接(详见 v6 plan §Phase B)。

- 用 svc_book 用户连 PG(对 shared.* 拥有完整读写权限)
- 提供 acquire() 上下文管理器获取连接
"""
import os
from contextlib import asynccontextmanager

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        user="svc_book",
        password=os.environ.get("POSTGRES_BOOK_PASSWORD", "minbook_dev"),
        database=os.environ.get("POSTGRES_DB", "minbook"),
        min_size=2,
        max_size=10,
    )


async def close_db():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def acquire():
    if _pool is None:
        raise RuntimeError("DB pool not initialized; call init_db() first")
    async with _pool.acquire() as conn:
        yield conn
