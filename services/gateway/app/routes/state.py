"""状态路由:代理到 state-service(详见 v2 plan §Phase C,fix v2-PhaseC)。

- /api/books/{book_id}/state/{file_type}              GET  → state-service /internal/state/{book_id}/truth/{file_type}
- /api/books/{book_id}/state/{file_type}              PUT  → state-service /internal/state/{book_id}/truth/{file_type}
- /api/books/{book_id}/snapshots                      GET  → state-service /internal/state/{book_id}/snapshots
- /api/books/{book_id}/snapshots                      POST → state-service /internal/state/{book_id}/snapshot

路径与 state-service 对齐(/internal/state/{book_id}/truth/{file_type} 含 book_id)。
"""
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/{book_id}/state/{file_type}")
async def get_truth(book_id: UUID, file_type: str, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.state_service_url}/internal/state/{book_id}/truth/{file_type}"
        )
        r.raise_for_status()
        return r.json()


class TruthUpdateBody(BaseModel):
    content: dict[str, Any]
    expected_version: int | None = None


@router.put("/{book_id}/state/{file_type}")
async def update_truth(
    book_id: UUID, file_type: str, body: TruthUpdateBody, user=Depends(verify_user_token)
):
    async with SignedHTTPClient("gateway") as client:
        r = await client.put(
            f"{settings.state_service_url}/internal/state/{book_id}/truth/{file_type}",
            json=body.model_dump(),
        )
        # 透传 409(乐观并发冲突)
        if r.status_code == 409:
            from fastapi import HTTPException
            raise HTTPException(409, detail=r.json().get("detail", r.text))
        r.raise_for_status()
        return r.json()


@router.get("/{book_id}/snapshots")
async def list_snapshots(book_id: UUID, request: Request, user=Depends(verify_user_token)):
    limit = request.query_params.get("limit", "20")
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.state_service_url}/internal/state/{book_id}/snapshots",
            params={"limit": limit},
        )
        r.raise_for_status()
        return r.json()


class SnapshotCreateBody(BaseModel):
    book_id: UUID
    chapter_number: int | None = None
    snapshot_json: dict[str, Any]


@router.post("/{book_id}/snapshots")
async def create_snapshot(
    book_id: UUID, body: SnapshotCreateBody, user=Depends(verify_user_token)
):
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.state_service_url}/internal/state/{book_id}/snapshot",
            json=body.model_dump(mode="json"),
        )
        r.raise_for_status()
        return r.json()
