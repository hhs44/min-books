"""写作工作台路由:SSE 代理(详见 v2 plan §3.3 sync/async 矩阵)。

- POST /api/books/{book_id}/write/next
  同步提交写作任务(返回 task_id,后续用 stream 端点获取进度)
- GET /api/books/{book_id}/write/stream/{task_id}
  SSE 流式输出(从 pipeline-orchestrator 透传)
  关键:禁用 Nginx buffer(`X-Accel-Buffering: no` header)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/{book_id}/write/next")
async def write_next(book_id: UUID, body: dict, user=Depends(verify_user_token)):
    """同步提交(返回 task_id,后续用 stream 获取进度)。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.pipeline_orchestrator_url}/internal/pipeline/write/next",
            json={"book_id": str(book_id), **body},
        )
        r.raise_for_status()
        return r.json()


@router.get("/{book_id}/write/stream/{task_id}")
async def write_stream(
    book_id: UUID,
    task_id: UUID,
    request: Request,
    user=Depends(verify_user_token),
):
    """SSE 流式输出(禁用 buffer)。"""
    async def event_generator():
        async with SignedHTTPClient("gateway") as client:
            async with client.stream(
                "GET",
                f"{settings.pipeline_orchestrator_url}/internal/pipeline/write/stream/{task_id}",
                params={"book_id": str(book_id)},
            ) as r:
                async for chunk in r.aiter_bytes():
                    if await request.is_disconnected():
                        break
                    yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
