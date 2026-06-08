"""内部服务间 HMAC 验证(详见 §13 §3.3)。"""
import os

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from ..auth import INTERNAL_SERVICE_ALLOWLIST, verify_internal_signature


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/internal/"):
            return await call_next(request)

        signature = request.headers.get("X-Service-Signature")
        service_id = request.headers.get("X-Service-Id")
        if not signature or not service_id:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Missing internal auth headers",
            )
        if service_id not in INTERNAL_SERVICE_ALLOWLIST:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Service {service_id} not allowed",
            )

        body = await request.body()
        secret = os.environ.get("SERVICE_SECRET", "")
        if not verify_internal_signature(
            request.method, request.url.path, body, signature, service_id, secret,
        ):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid signature",
            )

        return await call_next(request)
