"""通知渠道管理路由:代理到 notification-service。"""
from uuid import UUID

from fastapi import APIRouter, Depends
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/channels")
async def list_channels(user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(f"{settings.notification_service_url}/internal/channels")
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
async def update_channel(channel_id: str, body: dict, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.put(
            f"{settings.notification_service_url}/internal/channels/{channel_id}",
            json=body,
        )
        r.raise_for_status()
        return r.json()


@router.post("/test/{channel_id}")
async def test_channel(channel_id: str, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(
            f"{settings.notification_service_url}/internal/channels/{channel_id}/test"
        )
        r.raise_for_status()
        return {"status": "ok"}
