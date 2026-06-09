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
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "书籍列表", icon: BookOpen },
  { href: "/write", label: "写作工作台", icon: PenTool },
  { href: "/state", label: "真相文件", icon: FileText },
  { href: "/cost", label: "成本 & 监控", icon: BarChart3 },
  { href: "/observability", label: "链路追踪", icon: Activity },
  { href: "/agents", label: "Agents", icon: Cpu },
  { href: "/notifications", label: "通知配置", icon: Bell },
  { href: "/settings", label: "设置", icon: Settings },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav className={cn("flex flex-col gap-1 p-4 bg-gray-50 border-r", className)}>
      <div className="text-2xl font-bold mb-6 px-3 text-gray-900">MinBook</div>
      {NAV.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
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
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
