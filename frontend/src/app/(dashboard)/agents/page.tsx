"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function AgentsPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.listAgents(),
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold text-gray-900">Agents</h1>
      <p className="text-sm text-gray-500">实时 agent 注册表(v4 pipeline 端点)</p>

      {isLoading && <div className="text-gray-500 text-sm">加载中...</div>}
      {error && (
        <div className="text-red-600 text-sm">加载失败:{(error as Error)?.message}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {(data ?? []).map((a) => (
          <Card key={a.agent_id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-sm">
                <span className="font-mono">{a.agent_id}</span>
                <Badge
                  variant={
                    a.status === "idle" || a.status === "ready"
                      ? "default"
                      : a.status === "busy"
                        ? "secondary"
                        : a.status === "stale" || a.status === "dead"
                          ? "destructive"
                          : "outline"
                  }
                >
                  {a.status}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-gray-500 space-y-1">
              <p>类型: {a.agent_type ?? "—"}</p>
              {a.current_task && <p>当前任务: {a.current_task}</p>}
              {a.last_heartbeat && (
                <p>心跳: {new Date(a.last_heartbeat).toLocaleString()}</p>
              )}
            </CardContent>
          </Card>
        ))}
        {(!data || data.length === 0) && !isLoading && (
          <Card className="md:col-span-3">
            <CardContent className="text-center py-12 text-gray-500">
              暂无注册的 agent
            </CardContent>
          </Card>
        )}
      </div>

      <button
        onClick={() => refetch()}
        className="text-sm text-blue-600 hover:underline"
      >
        手动刷新
      </button>
    </div>
  );
}
