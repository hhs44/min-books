"use client";
import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, type CostThresholds } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  const { data: config, refetch: refetchConfig } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig(),
  });
  const { data: thresholds, refetch: refetchThresholds } = useQuery({
    queryKey: ["cost", "thresholds"],
    queryFn: () => api.getCostThresholds(),
  });

  const [thresholdDraft, setThresholdDraft] = useState<CostThresholds>({
    daily_usd: 20,
    monthly_usd: 500,
    per_book_usd: 100,
    spike_multiplier: 3,
  });
  useEffect(() => {
    if (thresholds) setThresholdDraft(thresholds);
  }, [thresholds]);

  const updateThreshold = useMutation({
    mutationFn: (t: CostThresholds) => api.updateCostThresholds(t),
    onSuccess: () => refetchThresholds(),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-3xl font-bold text-gray-900">设置</h1>

      <Card>
        <CardHeader>
          <CardTitle>LLM 成本告警阈值</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-sm font-medium block mb-1">每日阈值(USD)</label>
            <Input
              type="number"
              value={thresholdDraft.daily_usd}
              onChange={(e) =>
                setThresholdDraft({
                  ...thresholdDraft,
                  daily_usd: parseFloat(e.target.value || "0"),
                })
              }
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">每月阈值(USD)</label>
            <Input
              type="number"
              value={thresholdDraft.monthly_usd}
              onChange={(e) =>
                setThresholdDraft({
                  ...thresholdDraft,
                  monthly_usd: parseFloat(e.target.value || "0"),
                })
              }
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">单书阈值(USD)</label>
            <Input
              type="number"
              value={thresholdDraft.per_book_usd}
              onChange={(e) =>
                setThresholdDraft({
                  ...thresholdDraft,
                  per_book_usd: parseFloat(e.target.value || "0"),
                })
              }
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">
              突增倍数(对比过去 7 天同时段平均)
            </label>
            <Input
              type="number"
              step="0.1"
              value={thresholdDraft.spike_multiplier}
              onChange={(e) =>
                setThresholdDraft({
                  ...thresholdDraft,
                  spike_multiplier: parseFloat(e.target.value || "0"),
                })
              }
            />
          </div>
          {updateThreshold.error && (
            <p className="text-xs text-red-600">
              保存失败:{(updateThreshold.error as Error)?.message}
            </p>
          )}
          {updateThreshold.isSuccess && (
            <p className="text-xs text-green-600">已保存</p>
          )}
          <Button
            onClick={() => updateThreshold.mutate(thresholdDraft)}
            disabled={updateThreshold.isPending}
          >
            {updateThreshold.isPending ? "保存中..." : "保存"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>系统信息</CardTitle>
        </CardHeader>
        <CardContent>
          <DoctorStatus />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>当前配置(只读)</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto max-h-80 font-mono">
            {JSON.stringify(config, null, 2)}
          </pre>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchConfig()}
            className="mt-2"
          >
            刷新
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function DoctorStatus() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["doctor"],
    queryFn: () => api.doctor(),
    refetchInterval: 30_000,
  });
  if (isLoading) return <div className="text-gray-500 text-sm">检查中...</div>;
  if (error)
    return (
      <div className="text-red-600 text-sm">无法连接 Gateway:{(error as Error).message}</div>
    );
  if (!data) return null;
  return (
    <div className="space-y-2">
      <div>
        整体状态:{" "}
        <span
          className={data.status === "healthy" ? "text-green-600 font-medium" : "text-red-600 font-medium"}
        >
          {data.status}
        </span>
      </div>
      <ul className="text-sm space-y-1">
        {data.services.map((s) => (
          <li key={s.name} className="flex items-center justify-between">
            <span>
              {s.name}{" "}
              <span className="text-xs text-gray-400">({s.url})</span>
            </span>
            <span
              className={
                s.status === "healthy" ? "text-green-600" : "text-red-600"
              }
            >
              {s.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
