"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth";
import { Button } from "@/components/ui/button";
import { LogOut, User } from "lucide-react";

export function Header() {
  const router = useRouter();
  const { user, logout, fetchMe } = useAuthStore();

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="border-b h-14 flex items-center justify-between px-6 bg-white">
      <div className="text-sm text-gray-500">MinBook · 多智能体小说写作系统</div>
      <div className="flex items-center gap-4">
        {user && (
          <span className="flex items-center gap-2 text-sm text-gray-700">
            <User className="h-4 w-4" />
            {user.sub}
          </span>
        )}
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4 mr-2" /> 登出
        </Button>
      </div>
    </header>
  );
}
