"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";
import { NextIntlClientProvider } from "next-intl";
import { useState, type ReactNode } from "react";
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
  const locale = resolveLocale();
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