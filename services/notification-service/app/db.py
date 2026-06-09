"""notification-service 专用 DB 连接(详见 v2 plan §Phase D Task 24)。

- 用 svc_notify 用户连 PG(只能读写 notification.* schema)
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
        user="svc_notify",
        password=os.environ.get("POSTGRES_NOTIFY_PASSWORD", "minbook_dev"),
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
