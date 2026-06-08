"""异步 engine + session factory(每个服务进程共享)。"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from minbook_common.config import get_settings

_settings = get_settings()

# async engine,单服务内共享
engine = create_async_engine(
    _settings.postgres_dsn,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency:每个请求一个 session。"""
    async with AsyncSessionLocal() as session:
        yield session
