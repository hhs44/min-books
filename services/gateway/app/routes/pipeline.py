"""Pipeline 状态查询代理(v4 §Phase D Task 17)。

- GET /api/books/{book_id}/write/tasks/{task_id}
    代理到 pipeline-orchestrator /internal/pipeline/status/{run_id}

主路径(POST /api/books/{book_id}/write/next + SSE)已在 write_proxy.py 实现。
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/{book_id}/write/tasks/{task_id}")
async def get_write_task(
    book_id: UUID,
    task_id: UUID,
    user=Depends(verify_user_token),
):
    """查询写作任务状态(代理到 pipeline-orchestrator)。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.pipeline_orchestrator_url}/internal/pipeline/status/{task_id}",
        )
        if r.status_code == 404:
            raise HTTPException(404, f"Pipeline run {task_id} not found")
        r.raise_for_status()
        data = r.json()
    # 校验该 run 是否属于该 book
    if str(data.get("book_id", "")) != str(book_id):
        raise HTTPException(404, f"Pipeline run {task_id} not found for book {book_id}")
    return data
