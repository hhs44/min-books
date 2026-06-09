"""DLQ 管理代理路由(v4 §Phase D Task 17/18 补完)。

- GET    /api/dlq?status=&limit=        → 列表
- GET    /api/dlq/stats                 → 汇总
- GET    /api/dlq/{run_id}             → 详情
- POST   /api/dlq/{run_id}/retry       → 重试
- DELETE /api/dlq/{run_id}             → 标 dropped

代理到 pipeline-orchestrator /internal/dlq/*。
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("")
async def list_dlq(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    user=Depends(verify_user_token),
):
    """列出 DLQ 记录。"""
    async with SignedHTTPClient("gateway") as client:
        params = {"limit": limit}
        if status:
            params["status"] = status
        r = await client.get(
            f"{settings.pipeline_orchestrator_url}/internal/dlq",
            params=params,
        )
        r.raise_for_status()
        return r.json()


@router.get("/stats")
async def stats(user=Depends(verify_user_token)):
    """DLQ 汇总。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.pipeline_orchestrator_url}/internal/dlq/stats"
        )
        r.raise_for_status()
        return r.json()


@router.get("/{run_id}")
async def show(run_id: UUID, user=Depends(verify_user_token)):
    """DLQ 详情。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.pipeline_orchestrator_url}/internal/dlq/{run_id}"
        )
        if r.status_code == 404:
            raise HTTPException(404, f"DLQ entry {run_id} not found")
        r.raise_for_status()
        return r.json()


@router.post("/{run_id}/retry")
async def retry_run(run_id: UUID, user=Depends(verify_user_token)):
    """DLQ 重试(从最后成功节点创建新 run)。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.pipeline_orchestrator_url}/internal/dlq/{run_id}/retry"
        )
        if r.status_code == 404:
            raise HTTPException(404, f"DLQ entry {run_id} not found")
        r.raise_for_status()
        return r.json()


@router.delete("/{run_id}")
async def drop(run_id: UUID, user=Depends(verify_user_token)):
    """DLQ 标 dropped。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.delete(
            f"{settings.pipeline_orchestrator_url}/internal/dlq/{run_id}"
        )
        if r.status_code == 404:
            raise HTTPException(404, f"DLQ entry {run_id} not found")
        r.raise_for_status()
        return r.json()
