"""v3 agent-reviewer 测试 conftest。

- pytest-asyncio
- respx 友好的 mock fixtures
- 禁用系统代理避免 httpx SOCKS 报错
"""
import os
import pytest

# 在导入 httpx 之前禁用系统代理(避免 SOCKS proxy 报错)
for _k in (
    "ALL_PROXY", "all_proxy",
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "NO_PROXY", "no_proxy",
):
    os.environ.pop(_k, None)
os.environ["HTTPX_DISABLE_PROXY"] = "1"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


class _StubMemory:
    """memory 桩:recall 返空、store/load_procedural 不抛、pool=None(写表失败优雅降级)。"""

    async def recall(self, *a, **kw):
        return []

    async def store_episode(self, *a, **kw):
        return "stub-id"

    async def load_procedural(self, *a, **kw):
        return None

    @property
    def pool(self):
        raise RuntimeError("no pool (stub)")
