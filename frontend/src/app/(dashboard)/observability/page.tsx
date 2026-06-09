"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const GRAFANA = process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001";

export default function ObservabilityPage() {
  const [traceId, setTraceId] = useState("");
  const [dashboard, setDashboard] = useState(
    process.env.NEXT_PUBLIC_GRAFANA_DEFAULT_DASHBOARD || "system-overview",
  );

  const grafanaUrl = traceId
    ? `${GRAFANA}/explore?orgId=1&left=${encodeURIComponent(
        JSON.stringify({
          queries: [{ refId: "A", query: traceId, queryType: "traceql" }],
        }),
      )}`
    : `${GRAFANA}/d/${dashboard}`;

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold text-gray-900">链路追踪</h1>

      <Card>
        <CardHeader>
          <CardTitle>查看指定 Trace</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="输入 trace_id(如 abc123...)"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
            />
            <Button onClick={() => setTraceId(traceId)}>查询</Button>
            <Button variant="outline" onClick={() => setTraceId("")}>
              清空
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Grafana 仪表盘</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 mb-3">
            {[
              "system-overview",
              "per-service",
              "pipeline-detail",
              "llm-cost",
              "nats",
            ].map((d) => (
              <Button
                key={d}
                variant={dashboard === d ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setDashboard(d);
                  setTraceId("");
                }}
              >
                {d}
              </Button>
            ))}
          </div>
          <iframe
            src={grafanaUrl}
            className="w-full border rounded bg-white"
            style={{ height: "calc(100vh - 280px)", minHeight: 400 }}
            title="Grafana Dashboard"
          />
        </CardContent>
      </Card>
    </div>
  );
}
