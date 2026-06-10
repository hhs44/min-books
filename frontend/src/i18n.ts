// frontend/src/i18n.ts
// v6 Phase C: locale 改从 cookie 读(set by middleware.ts)。
// Client 端通过 `document.cookie` 读,server 端可通过 `cookies()` 读。
// 保留 NEXT_PUBLIC_DEFAULT_LOCALE 作为兜底(SSR 初次渲染,cookie 还没注入)。

import zh from "../messages/zh.json";
import en from "../messages/en.json";
import ja from "../messages/ja.json";

export const messages = { zh, en, ja } as const;
export type SupportedLocale = keyof typeof messages;

export const DEFAULT_LOCALE: SupportedLocale = "zh";
export const SUPPORTED_LOCALES: SupportedLocale[] = ["zh", "en", "ja"];

export function isSupportedLocale(v: string | null | undefined): v is SupportedLocale {
  return v === "zh" || v === "en" || v === "ja";
}

export function getMessages(locale: SupportedLocale) {
  return messages[locale];
}

/**
 * 在 client 组件中解析 locale(读 document.cookie 中的 minbook_locale)。
 * 在 server 组件中(没有 document)应通过 next/headers.cookies() 读取,这里不导。
 */
export function resolveLocale(): SupportedLocale {
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)minbook_locale=([^;]+)/);
    const raw = match ? decodeURIComponent(match[1]) : null;
    if (isSupportedLocale(raw)) return raw;
  }
  const envDefault = process.env.NEXT_PUBLIC_DEFAULT_LOCALE;
  if (isSupportedLocale(envDefault)) return envDefault;
  return DEFAULT_LOCALE;
}
