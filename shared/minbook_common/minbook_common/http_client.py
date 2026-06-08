"""带内部 HMAC 签名的 httpx async client(详见 §13 §3.2)。"""
import hashlib
import hmac
import json
import os
from urllib.parse import urlparse

import httpx

from .auth import INTERNAL_SERVICE_ALLOWLIST  # noqa: F401  (re-exported)


class SignedHTTPClient(httpx.AsyncClient):
    """每个服务用这个 client 调内部 /internal/ 接口,自动加签名。"""

    def __init__(self, service_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name
        self.secret = os.environ.get("SERVICE_SECRET", "").encode("utf-8")

    async def request(self, method, url, **kwargs):
        body = kwargs.get("content") or b""
        if "json" in kwargs and kwargs["json"] is not None:
            body = json.dumps(kwargs["json"], separators=(",", ":")).encode()

        parsed = urlparse(str(url))
        if parsed.path.startswith("/internal/") and self.secret:
            body_hash = hashlib.sha256(body).hexdigest()
            msg = f"{method.upper()}:{parsed.path}:{body_hash}"
            sig = hmac.new(self.secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()
            headers = kwargs.pop("headers", {}) or {}
            headers["X-Service-Id"] = self.service_name
            headers["X-Service-Signature"] = sig
            kwargs["headers"] = headers

        return await super().request(method, url, **kwargs)
