"""LLM 配置路由:代理到 llm-gateway(详见 v2 plan §12)。

- GET /api/llm/providers -> llm-gateway /internal/llm/providers
- GET /api/llm/models    -> llm-gateway /internal/llm/models
- POST /api/llm/test     -> llm-gateway /internal/llm/test
"""
from fastapi import APIRouter, Depends
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/providers")
async def list_providers(user=Depends(verify_user_token)):
    """列出支持的 LLM 服务商。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(f"{settings.llm_gateway_url}/internal/llm/providers")
        r.raise_for_status()
        return r.json()


@router.get("/models")
async def list_models(user=Depends(verify_user_token)):
    """列出可用模型(带定价)。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.get(f"{settings.llm_gateway_url}/internal/llm/models")
        r.raise_for_status()
        return r.json()


@router.post("/test")
async def test_connection(body: dict, user=Depends(verify_user_token)):
    """测试 LLM 连接(用 mini prompt)。"""
    async with SignedHTTPClient("gateway") as client:
        r = await client.post(f"{settings.llm_gateway_url}/internal/llm/test", json=body)
        r.raise_for_status()
        return r.json()
