"""简单 i18n:从 Accept-Language header 解析,注入 request.state.locale(详见 v2 plan §Phase A Task 4)。

- 支持 `zh / en / ja`(可在 Settings 里配)
- 取语言 tag 的前半(`zh-CN` -> `zh`)
- 找不到时用 default_locale
"""
from starlette.middleware.base import BaseHTTPMiddleware


class I18nMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_locale: str = "zh", supported: list[str] | None = None):
        super().__init__(app)
        self.default_locale = default_locale
        self.supported = supported or ["zh"]

    async def dispatch(self, request, call_next):
        accept_lang = request.headers.get("Accept-Language", "")
        locale = self._parse(accept_lang) or self.default_locale
        request.state.locale = locale
        return await call_next(request)

    def _parse(self, header: str) -> str | None:
        if not header:
            return None
        for part in header.split(","):
            lang = part.split(";")[0].strip().lower()
            base = lang.split("-")[0]  # zh-CN -> zh
            if base in self.supported:
                return base
        return None
