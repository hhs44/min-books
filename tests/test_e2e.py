"""v2 跨服务 e2e 集成测试(详见 v2 plan §Phase E Task 27)。

目的:从 gateway 端到端验证一次完整 PUT truth → state-service → DB。

运行(需要 gateway + state-service 容器在跑):
    uv run --package minbook-gateway pytest tests/test_e2e.py -v

依赖:容器的 ~/.minbook/auth.token 已存在(由 gateway 首次启动时生成)。
BOOK_ID:使用 shared.books 中已存在的测试 book。
"""
import os
from pathlib import Path

import httpx
import pytest

GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8000")
TOKEN_FILE = Path(os.environ.get("TOKEN_FILE", str(Path.home() / ".minbook" / "auth.token")))
# 共享测试 book_id(verify-v2.sh 也用此 id,需先通过 migrations 创建)
TEST_BOOK_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(scope="module")
def auth_headers() -> dict[str, str]:
    token = TOKEN_FILE.read_text().strip()
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_e2e_put_truth_then_read_back(auth_headers: dict[str, str]):
    """完整 e2e:gateway PUT truth → state-service → DB → GET 读回 version+1。"""
    file_type = "current_state"
    payload = {
        "content": {"e2e": True, "ts": "2026-06-09"},
        "expected_version": None,  # 强制覆盖
    }

    async with httpx.AsyncClient(base_url=GATEWAY, headers=auth_headers, timeout=10) as client:
        # 1) PUT
        put_resp = await client.put(
            f"/api/books/{TEST_BOOK_ID}/state/{file_type}", json=payload
        )
        assert put_resp.status_code == 200, (
            f"PUT failed: {put_resp.status_code} {put_resp.text}"
        )
        new_version = put_resp.json()["version"]
        assert isinstance(new_version, int) and new_version >= 1

        # 2) GET 读回,version 必须匹配,content 必须包含 e2e=True
        get_resp = await client.get(f"/api/books/{TEST_BOOK_ID}/state/{file_type}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["version"] == new_version
        assert body["content"].get("e2e") is True

        # 3) 用错版本号 PUT → 409 乐观并发冲突
        wrong_resp = await client.put(
            f"/api/books/{TEST_BOOK_ID}/state/{file_type}",
            json={"content": {"x": 1}, "expected_version": 99999},
        )
        assert wrong_resp.status_code == 409, (
            f"expected 409 conflict, got {wrong_resp.status_code}: {wrong_resp.text}"
        )


@pytest.mark.asyncio
async def test_e2e_snapshots_after_truth_put(auth_headers: dict[str, str]):
    """snapshots 列表可访问(Bug 1 修复后)。"""
    async with httpx.AsyncClient(base_url=GATEWAY, headers=auth_headers, timeout=10) as client:
        resp = await client.get(f"/api/books/{TEST_BOOK_ID}/state/snapshots")
        assert resp.status_code == 200, (
            f"snapshots route not 200: {resp.status_code} {resp.text}"
        )
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_e2e_doctor_reports_4_services(auth_headers: dict[str, str]):
    """/api/doctor 4 下游全 healthy。"""
    async with httpx.AsyncClient(base_url=GATEWAY, headers=auth_headers, timeout=10) as client:
        resp = await client.get("/api/doctor")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy", f"doctor degraded: {body}"
        names = {s["name"] for s in body["services"]}
        assert names == {
            "state-service",
            "llm-gateway",
            "notification-service",
            "pipeline-orchestrator",
        }
        for svc in body["services"]:
            assert svc["status"] == "healthy", f"{svc['name']} not healthy: {svc}"
