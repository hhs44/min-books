// frontend/src/i18n.ts
// Loads the message catalog for a given locale.
// This module is used directly (without next-intl/middleware) to populate
// NextIntlClientProvider in the root layout. Locale selection is read from
// the NEXT_PUBLIC_DEFAULT_LOCALE env var; a future iteration can wire this
// to a user preference stored in localStorage / cookie.

import zh from "../messages/zh.json";
import en from "../messages/en.json";
import ja from "../messages/ja.json";

export const messages = { zh, en, ja } as const;
export type SupportedLocale = keyof typeof messages;

export function resolveLocale(): SupportedLocale {
  const raw = process.env.NEXT_PUBLIC_DEFAULT_LOCALE;
  if (raw === "zh" || raw === "en" || raw === "ja") return raw;
  return "zh";
}

export function getMessages(locale: SupportedLocale) {
  return messages[locale];
}