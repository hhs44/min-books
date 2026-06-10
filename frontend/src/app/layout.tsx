import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "MinBook",
  description: "多智能体小说写作系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Server 组件能读 cookie;middleware 已注入,这里取不到 header,
  // 用环境变量作为 SSR 兜底,客户端 hydrate 后 Providers 会同步。
  return (
    <html lang="zh" suppressHydrationWarning>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
