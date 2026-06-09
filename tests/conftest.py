"""v2 e2e 测试的 conftest — 加 pytest-asyncio 模式。

让 tests/test_e2e.py 里的 @pytest.mark.asyncio 不用每个都写 loop fixture。
"""
import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
