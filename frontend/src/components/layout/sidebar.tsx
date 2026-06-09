"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  PenTool,
  FileText,
  Settings,
  Bell,
  BarChart3,
  Activity,
  Cpu,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

const NAV_KEYS = [
  { href: "/", key: "books", icon: BookOpen },
  { href: "/write", key: "write", icon: PenTool },
  { href: "/state", key: "state", icon: FileText },
  { href: "/cost", key: "cost", icon: BarChart3 },
  { href: "/observability", key: "observability", icon: Activity },
  { href: "/agents", key: "agents", icon: Cpu },
  { href: "/notifications", key: "notifications", icon: Bell },
  { href: "/settings", key: "settings", icon: Settings },
] as const;

export function Sidebar({ className }: { className?: string }) {
  const t = useTranslations("nav");
  const pathname = usePathname() ?? "";
  return (
    <nav className={cn("flex flex-col gap-1 p-4 bg-gray-50 border-r", className)}>
      <div className="text-2xl font-bold mb-6 px-3 text-gray-900">MinBook</div>
      {NAV_KEYS.map((item) => {
        const Icon = item.icon;
        const active =
          pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              active
                ? "bg-blue-600 text-white"
                : "text-gray-700 hover:bg-gray-200",
            )}
          >
            <Icon className="h-4 w-4" />
            {t(item.key)}
          </Link>
        );
      })}
    </nav>
  );
}