"""v3 agent-planner 测试 conftest。

- 启用 pytest-asyncio
- 暴露 respx 友好的 mock fixtures
"""
import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
