"use client";
import { useEffect, useRef } from "react";
import {
  useCostSummary,
  useDailyCosts,
  useCostByBook,
  useRecentCalls,
} from "@/lib/hooks/use-cost";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function CostPage() {
  const { data: summary } = useCostSummary();
  const { data: daily } = useDailyCosts(30);
  const { data: byBook } = useCostByBook();
  const { data: recent } = useRecentCalls(20);

  // Simple line chart on canvas
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvasRef.current || !daily) return;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;
    const w = canvasRef.current.width;
    const h = canvasRef.current.height;
    ctx.clearRect(0, 0, w, h);

    if (daily.length === 0) return;

    const maxCost = Math.max(...daily.map((d) => d.cost), 1);
    const xStep = w / Math.max(daily.length - 1, 1);

    // grid
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = (h / 4) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // line
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.beginPath();
    daily.forEach((d, i) => {
      const x = i * xStep;
      const y = h - (d.cost / maxCost) * (h - 20) - 10;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // dots
    ctx.fillStyle = "#2563eb";
    daily.forEach((d, i) => {
      const x = i * xStep;
      const y = h - (d.cost / maxCost) * (h - 20) - 10;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [daily]);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">LLM 成本</h1>

      {/* Top 4 numbers */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">今日</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-gray-900">
            ${summary?.today?.toFixed(2) ?? "0.00"}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">本周</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-gray-900">
            ${summary?.this_week?.toFixed(2) ?? "0.00"}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">本月</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-gray-900">
            ${summary?.this_month?.toFixed(2) ?? "0.00"}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">本年</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold text-gray-900">
            ${summary?.this_year?.toFixed(2) ?? "0.00"}
          </CardContent>
        </Card>
      </div>

      {/* 30-day line chart */}
      <Card>
        <CardHeader>
          <CardTitle>每日成本(过去 30 天)</CardTitle>
        </CardHeader>
        <CardContent>
          <canvas
            ref={canvasRef}
            width={800}
            height={200}
            className="w-full"
            aria-label="Daily cost line chart"
          />
        </CardContent>
      </Card>

      {/* Top 10 books */}
      <Card>
        <CardHeader>
          <CardTitle>单书成本 Top 10</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>书名</TableHead>
                <TableHead className="text-right">成本</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(byBook ?? []).slice(0, 10).map((b) => (
                <TableRow key={b.book_id}>
                  <TableCell>{b.title || b.book_id}</TableCell>
                  <TableCell className="text-right">${b.cost.toFixed(4)}</TableCell>
                </TableRow>
              ))}
              {(!byBook || byBook.length === 0) && (
                <TableRow>
                  <TableCell colSpan={2} className="text-center text-gray-500">
                    暂无数据
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Recent calls */}
      <Card>
        <CardHeader>
          <CardTitle>最近 LLM 调用</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>时间</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right">Latency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(recent ?? []).map((c: any, i) => (
                <TableRow key={i}>
                  <TableCell className="text-xs">
                    {c.created_at ? new Date(c.created_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell>{c.provider ?? "—"}</TableCell>
                  <TableCell className="text-xs">{c.model ?? "—"}</TableCell>
                  <TableCell className="text-xs">{c.agent_id ?? "—"}</TableCell>
                  <TableCell className="text-right">
                    {(c.prompt_tokens ?? 0) + (c.completion_tokens ?? 0)}
                  </TableCell>
                  <TableCell className="text-right">
                    ${(c.cost_estimate ?? 0).toFixed(4)}
                  </TableCell>
                  <TableCell className="text-right">
                    {c.latency_ms ? `${c.latency_ms} ms` : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {(!recent || recent.length === 0) && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-500">
                    暂无调用
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
