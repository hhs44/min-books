"""全局配置路由:代理到 state-service(详见 v2 plan §12 §3.1)。"""
from fastapi import APIRouter, Depends
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("")
async def get_config(user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(f"{settings.state_service_url}/internal/config")
        r.raise_for_status()
        return r.json()


class ConfigUpdate(BaseModel):
    config_key: str
    config_value: dict


@router.put("")
async def update_config(body: ConfigUpdate, user=Depends(verify_user_token)):
    async with SignedHTTPClient("gateway") as client:
        r = await client.put(
            f"{settings.state_service_url}/internal/config",
            json=body.model_dump(),
        )
        r.raise_for_status()
        return {"status": "ok"}
