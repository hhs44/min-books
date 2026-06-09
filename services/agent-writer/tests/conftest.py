"""v3 agent-writer 测试 conftest。

- pytest-asyncio
- respx 友好的 mock fixtures
"""
import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
