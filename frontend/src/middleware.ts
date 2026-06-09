// frontend/src/middleware.ts
// Intentionally minimal: full next-intl App Router routing would require
// moving all pages under a `[locale]` segment. For this v5 release we
// keep the default-locale routing strategy (default = zh) and ship the
// 3-locale message catalogs so `useTranslations("nav")` works wherever
// the strings are wired up. Locale switching can be wired in later via
// a cookie + a manual rewrite of <html lang>.

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(_request: NextRequest) {
  // pass-through
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};