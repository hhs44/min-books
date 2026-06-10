// frontend/src/middleware.ts
// v6 Phase C:URL-based locale routing with cookie persistence + middleware rewrite.
//
// - `/`               → 307 redirect to `/zh/` (default locale)
// - `/zh/...`         → rewrite to internal `/...` + set `x-minbook-locale=zh` cookie/header
// - `/en/...`         → rewrite to internal `/...` + set `x-minbook-locale=en` cookie/header
// - `/ja/...`         → rewrite to internal `/...` + set `x-minbook-locale=ja` cookie/header
// - 其它(无 locale 前缀)→ 用 cookie 里的 locale 作 rewrite,没有 cookie 则重定向到 `/zh/...`
//
// 这种"rewrite 模式"避免了把所有 9 个页面迁到 `[locale]/` segment(那是
// 200+ 文件改动,容易在 v6 时间预算内翻车)。代价是 URL 看起来有 locale 前缀,
// 但内部路由还是 `/login`、`/books` 等。

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const DEFAULT_LOCALE = "zh";
const SUPPORTED = ["zh", "en", "ja"] as const;
type Locale = (typeof SUPPORTED)[number];

const LOCALE_COOKIE = "minbook_locale";
const LOCALE_HEADER = "x-minbook-locale";

function isLocale(value: string | undefined | null): value is Locale {
  return value === "zh" || value === "en" || value === "ja";
}

function detectLocale(request: NextRequest): { locale: Locale; fromUrl: boolean } {
  // 1. URL 路径前缀优先级最高
  for (const loc of SUPPORTED) {
    if (
      request.nextUrl.pathname === `/${loc}` ||
      request.nextUrl.pathname.startsWith(`/${loc}/`)
    ) {
      return { locale: loc, fromUrl: true };
    }
  }
  // 2. 已有 cookie
  const cookieLocale = request.cookies.get(LOCALE_COOKIE)?.value;
  if (isLocale(cookieLocale)) {
    return { locale: cookieLocale, fromUrl: false };
  }
  // 3. Accept-Language header(简单匹配)
  const accept = request.headers.get("accept-language") || "";
  for (const loc of SUPPORTED) {
    if (accept.toLowerCase().includes(loc)) {
      return { locale: loc, fromUrl: false };
    }
  }
  return { locale: DEFAULT_LOCALE, fromUrl: false };
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // 跳过 API、静态资源、_next
  if (
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/_vercel/") ||
    /\.[a-zA-Z0-9]+$/.test(pathname)
  ) {
    return NextResponse.next();
  }

  const { locale, fromUrl } = detectLocale(request);

  // 情况 1:URL 不带 locale 前缀 → 重定向到 /<locale>/...
  if (!fromUrl) {
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
    url.search = search;
    const response = NextResponse.redirect(url, 307);
    response.cookies.set(LOCALE_COOKIE, locale, {
      maxAge: 60 * 60 * 24 * 365,
      path: "/",
      sameSite: "lax",
    });
    return response;
  }

  // 情况 2:URL 带 locale 前缀 → 改写(rewrite)到内部路径,传递 locale header + 同步 cookie
  const stripped = pathname.replace(/^\/(zh|en|ja)/, "") || "/";
  const url = request.nextUrl.clone();
  url.pathname = stripped;
  url.search = search;

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(LOCALE_HEADER, locale);

  const response = NextResponse.rewrite(url, {
    request: { headers: requestHeaders },
  });
  // 写 cookie 让后续无前缀 URL 也能记住选择
  response.cookies.set(LOCALE_COOKIE, locale, {
    maxAge: 60 * 60 * 24 * 365,
    path: "/",
    sameSite: "lax",
  });
  return response;
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
