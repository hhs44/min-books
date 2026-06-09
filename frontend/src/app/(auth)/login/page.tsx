"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function LoginPage() {
  const router = useRouter();
  const { tokenInput, setToken, login, loading, error, user, fetchMe } = useAuthStore();
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  useEffect(() => {
    if (user) router.push("/");
  }, [user, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>MinBook 登录</CardTitle>
          <CardDescription>
            从 <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">~/.minbook/auth.token</code>{" "}
            复制 token 粘贴
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            type="password"
            placeholder="粘贴 JWT token..."
            value={tokenInput}
            onChange={(e) => setToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && tokenInput && login()}
          />
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button
            onClick={login}
            disabled={loading || !tokenInput}
            className="w-full"
          >
            {loading ? "登录中..." : "登录"}
          </Button>
          <Button
            variant="link"
            size="sm"
            onClick={() => setShowHint(!showHint)}
            className="px-0"
          >
            找不到 token?
          </Button>
          {showHint && (
            <div className="text-xs text-gray-500 space-y-1">
              <p>Token 启动时由 Gateway 自动生成。重启 Gateway 服务会重新生成。</p>
              <p>
                查看方式: <code>cat ~/.minbook/auth.token</code>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
