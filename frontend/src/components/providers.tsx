"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";
import { NextIntlClientProvider } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import { resolveLocale, getMessages } from "@/i18n";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 5_000, refetchOnWindowFocus: false, retry: 1 },
        },
      }),
  );
  // 初次渲染用默认 locale,客户端 hydrate 后再读 cookie 真实 locale
  const [locale, setLocale] = useState(() => resolveLocale());
  useEffect(() => {
    setLocale(resolveLocale());
  }, []);
  const msgs = getMessages(locale);
  return (
    <NextIntlClientProvider locale={locale} messages={msgs}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <QueryClientProvider client={queryClient}>
          {children}
          {process.env.NODE_ENV === "development" && <ReactQueryDevtools />}
        </QueryClientProvider>
      </ThemeProvider>
    </NextIntlClientProvider>
  );
}
