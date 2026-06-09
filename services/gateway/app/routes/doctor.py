"""配置诊断路由:并发检查所有下游服务(详见 v2 plan §Phase A Task 7)。"""
import asyncio

from fastapi import APIRouter, Depends
from minbook_common.http_client import SignedHTTPClient
from minbook_common.middleware import verify_user_token

from ..config import get_settings

router = APIRouter()
settings = get_settings()


async def check(name: str, url: str, path: str = "/health") -> dict:
    try:
        async with SignedHTTPClient("gateway") as client:
            r = await client.get(f"{url}{path}", timeout=5)
            return {
                "name": name,
                "status": "healthy" if r.status_code == 200 else f"unhealthy_{r.status_code}",
                "url": url,
            }
    except Exception as e:
        return {"name": name, "status": "unreachable", "error": str(e), "url": url}


@router.get("")
async def doctor(user=Depends(verify_user_token)):
    """并发检查所有下游服务(4 个,含 plan v2 范围)。"""
    services = [
        ("state-service", settings.state_service_url),
        ("llm-gateway", settings.llm_gateway_url),
        ("notification-service", settings.notification_service_url),
        ("pipeline-orchestrator", settings.pipeline_orchestrator_url),
    ]
    results = await asyncio.gather(*[check(name, url) for name, url in services])
    all_healthy = all(r["status"] == "healthy" for r in results)
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": results,
    }
