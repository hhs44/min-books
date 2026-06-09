"""JWT 登录端点(详见 v2 plan §13 §5.2)。

- POST /api/auth/login: 验证用户在请求体里提供的 token(从 ~/.minbook/auth.token 复制),
  通过后写入 httpOnly cookie。
- POST /api/auth/logout: 删除 cookie。
- GET /api/auth/me: 返回当前用户(简化版,本计划 v2 不做完整 RBAC)。
"""
import os

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from minbook_common.auth import verify_jwt_token

router = APIRouter()


class LoginRequest(BaseModel):
    token: str  # 用户从 ~/.minbook/auth.token 复制


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise HTTPException(500, "JWT_SECRET not configured")

    try:
        verify_jwt_token(body.token, secret)
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")

    response.set_cookie(
        key="auth_token",
        value=body.token,
        httponly=True,
        secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        samesite="strict",
        max_age=365 * 24 * 3600,
        path="/",
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("auth_token", path="/")
    return {"status": "ok"}


@router.get("/me")
async def me():
    """返回当前用户(简化版:本计划 v2 只有单用户)。"""
    return {"sub": "local_user", "scope": ["read", "write", "admin"]}
