"""JWT 验证中间件(详见 §13 §2.2)。"""
import os

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from ..auth import TokenPayload, verify_jwt_token


async def verify_user_token(request: Request) -> TokenPayload:
    # Loopback bypass(本地开发:127.0.0.1, ::1, localhost)
    if os.environ.get("ALLOW_LOOPBACK_BYPASS", "true").lower() == "true":
        client_ip = request.client.host if request.client else ""
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return TokenPayload(
                sub="local_user",
                iat=0, exp=9999999999,
                scope=["read", "write", "admin"],
            )

    # 从 cookie 优先
    token = request.cookies.get("auth_token")
    if not token:
        scheme, param = get_authorization_scheme_param(
            request.headers.get("Authorization", "")
        )
        if scheme.lower() == "bearer" and param:
            token = param

    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")

    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "JWT_SECRET not configured",
        )

    try:
        return verify_jwt_token(token, secret)
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")
