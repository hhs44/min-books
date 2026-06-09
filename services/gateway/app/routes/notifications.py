"""通知渠道管理路由:代理到 notification-service(详见 v2 plan §Phase D)。

对外 /api/notifications/* 路径:
  - GET  /api/notifications/channels[?book_id=...]   列表(脱敏)
  - POST /api/notifications/channels                 新建
  - PUT  /api/notifications/channels/{id}            更新
  - POST /api/notifications/test/{channel_id}        测试单 channel
  - POST /api/notifications/notify/{book_id}         触发发通知
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/channels")
async def list_channels(
    book_id: UUID | None = Query(default=None),
    user=Depends(verify_user_token),
):
    params: dict = {}
    if book_id:
        params["book_id"] = str(book_id)
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(
            f"{settings.notification_service_url}/internal/channels",
            params=params,
        )
        r.raise_for_status()
        return r.json()


class ChannelCreate(BaseModel):
    book_id: UUID
    channel_type: str  # telegram | feishu | wechat_work | webhook
    config_json: dict
    enabled: bool = True


@router.post("/channels")
async def create_channel(body: ChannelCreate, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.notification_service_url}/internal/channels",
            json=body.model_dump(mode="json"),
        )
        r.raise_for_status()
        return r.json()


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: UUID, body: dict, user=Depends(verify_user_token)
):
    async with SignedHTTPClient("gateway") as client:
        r = await client.put(
            f"{settings.notification_service_url}/internal/channels/{channel_id}",
            json=body,
        )
        r.raise_for_status()
        return r.json()


@router.post("/test/{channel_id}")
async def test_channel(channel_id: UUID, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.notification_service_url}/internal/channels/{channel_id}/test"
        )
        r.raise_for_status()
        return r.json()


class NotifyRequest(BaseModel):
    title: str
    body: str
    level: str = "info"
    chapter_number: int | None = None
    details: dict | None = None


@router.post("/notify/{book_id}")
async def notify_book(
    book_id: UUID, payload: NotifyRequest, user=Depends(verify_user_token)
):
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.notification_service_url}/internal/notify/{book_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        r.raise_for_status()
        return r.json()
