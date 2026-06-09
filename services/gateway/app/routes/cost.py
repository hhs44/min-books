"""成本查询路由:代理到 llm-gateway /api/cost/*(详见 v2 plan §12)。

Phase B 添加:让 /api/cost/{summary,daily,by-book,recent-calls,thresholds} 透传到 llm-gateway。
需要保留用户 JWT(llm-gateway 的 cost route 用 verify_user_token)。
"""
import json

from fastapi import APIRouter, Depends, Request
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

router = APIRouter()
settings = get_settings()


async def _proxy(method: str, path: str, request: Request):
    auth_header = request.headers.get("authorization", "")
    async with SignedHTTPClient("gateway") as client:
        url = f"{settings.llm_gateway_url}/api/cost/{path}"
        kwargs = {"params": dict(request.query_params)}
        if auth_header:
            kwargs["headers"] = {"Authorization": auth_header}
        if method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if body:
                try:
                    kwargs["json"] = json.loads(body)
                except Exception:
                    pass
        r = await client.request(method, url, **kwargs)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        return r.json() if ct.startswith("application/json") else r.text


@router.get("/summary")
async def cost_summary(request: Request, user=Depends(verify_user_token)):
    return await _proxy("GET", "summary", request)


@router.get("/daily")
async def cost_daily(request: Request, user=Depends(verify_user_token)):
    return await _proxy("GET", "daily", request)


@router.get("/by-book")
async def cost_by_book(request: Request, user=Depends(verify_user_token)):
    return await _proxy("GET", "by-book", request)


@router.get("/recent-calls")
async def cost_recent_calls(request: Request, user=Depends(verify_user_token)):
    return await _proxy("GET", "recent-calls", request)


@router.put("/thresholds")
async def cost_thresholds(request: Request, user=Depends(verify_user_token)):
    return await _proxy("PUT", "thresholds", request)
