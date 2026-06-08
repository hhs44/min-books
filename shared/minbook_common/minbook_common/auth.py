"""JWT(user 鉴权) + 内部 HMAC 签名(服务间鉴权)。详见 §13。"""
import hashlib
import hmac
import logging
import time
from pathlib import Path

import jwt
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    sub: str
    iat: int
    exp: int
    scope: list[str]
    iss: str = "minbook-gateway"


def create_jwt_token(
    secret: str,
    subject: str = "local_user",
    scopes: list[str] | None = None,
    expiry_seconds: int = 365 * 24 * 3600,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expiry_seconds,
        "scope": scopes or ["read", "write", "admin"],
        "iss": "minbook-gateway",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_jwt_token(token: str, secret: str) -> TokenPayload:
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"require": ["sub", "exp", "scope"]},
    )
    return TokenPayload(**payload)


# === 内部服务间 HMAC 签名 ===

INTERNAL_SERVICE_ALLOWLIST = {
    "gateway",
    "pipeline-orchestrator",
    "agent-planner-service",
    "agent-writer-service",
    "agent-reviewer-service",
    "state-service",
    "llm-gateway",
    "notification-service",
    "book-service",
}


def sign_internal_request(method: str, path: str, body: bytes, secret: str) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    msg = f"{method.upper()}:{path}:{body_hash}"
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_internal_signature(
    method: str,
    path: str,
    body: bytes,
    signature: str,
    service_id: str,
    secret: str,
) -> bool:
    if service_id not in INTERNAL_SERVICE_ALLOWLIST:
        return False
    expected = sign_internal_request(method, path, body, secret)
    return hmac.compare_digest(expected, signature)


# === 本地 token 持久化(单机模式) ===

TOKEN_PATH = Path.home() / ".minbook" / "auth.token"


def _create(secret: str, expiry_seconds: int) -> str:
    token = create_jwt_token(secret, expiry_seconds=expiry_seconds)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    return token


def init_local_token(secret: str, expiry_seconds: int = 365 * 24 * 3600) -> str:
    """初始化并持久化本地 JWT token(单用户开发模式)。"""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_PATH.exists():
        existing = TOKEN_PATH.read_text().strip()
        try:
            verify_jwt_token(existing, secret)
            return existing
        except Exception as e:
            logger.debug(f"existing token invalid ({type(e).__name__}); rotating")
    return _create(secret, expiry_seconds)
