"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Plus, Send, Trash2, Power } from "lucide-react";

const CHANNEL_TYPES = [
  { value: "telegram", label: "Telegram Bot" },
  { value: "feishu", label: "飞书 Webhook" },
  { value: "wechat_work", label: "企业微信 Webhook" },
  { value: "webhook", label: "通用 Webhook" },
];

export default function NotificationsPage() {
  const qc = useQueryClient();
  const { data: channels } = useQuery({
    queryKey: ["channels"],
    queryFn: () => api.listChannels(),
  });
  const [showAdd, setShowAdd] = useState(false);
  const [newChannel, setNewChannel] = useState<{
    book_id: string;
    channel_type: string;
    config_json: string;
  }>({
    book_id: "",
    channel_type: "telegram",
    config_json: "{}",
  });

  const create = useMutation({
    mutationFn: () =>
      api.createChannel({
        book_id: newChannel.book_id,
        channel_type: newChannel.channel_type,
        config_json: JSON.parse(newChannel.config_json || "{}"),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["channels"] });
      setShowAdd(false);
      setNewChannel({ book_id: "", channel_type: "telegram", config_json: "{}" });
    },
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.updateChannel(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["channels"] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteChannel(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["channels"] }),
  });

  const test = useMutation({
    mutationFn: (id: string) => api.testChannel(id),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">通知渠道</h1>
        <Button onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4 mr-2" /> 添加渠道
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(channels ?? []).map((ch) => {
          const t = CHANNEL_TYPES.find((x) => x.value === ch.channel_type);
          return (
            <Card key={ch.id}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  <span>{t?.label ?? ch.channel_type}</span>
                  <Badge variant={ch.enabled ? "default" : "secondary"}>
                    {ch.enabled ? "启用" : "停用"}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs text-gray-500">Book: {ch.book_id}</p>
                <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-32 font-mono">
                  {JSON.stringify(ch.config_summary, null, 2)}
                </pre>
                {test.data && (
                  <p className="text-xs text-green-600">测试已发送:{test.data.status}</p>
                )}
                {test.error && (
                  <p className="text-xs text-red-600">
                    错误:{(test.error as Error)?.message}
                  </p>
                )}
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => test.mutate(ch.id)}
                    disabled={test.isPending}
                  >
                    <Send className="h-3 w-3 mr-1" /> 测试
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggle.mutate({ id: ch.id, enabled: !ch.enabled })}
                  >
                    <Power className="h-3 w-3 mr-1" />
                    {ch.enabled ? "停用" : "启用"}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      if (confirm("确认删除该渠道?")) remove.mutate(ch.id);
                    }}
                  >
                    <Trash2 className="h-3 w-3 mr-1" /> 删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {(!channels || channels.length === 0) && (
          <Card className="md:col-span-2">
            <CardContent className="text-center py-12 text-gray-500">
              尚未配置通知渠道
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加通知渠道</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1">Book ID</label>
              <Input
                placeholder="00000000-0000-0000-0000-000000000001"
                value={newChannel.book_id}
                onChange={(e) =>
                  setNewChannel({ ...newChannel, book_id: e.target.value })
                }
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">渠道类型</label>
              <Select
                value={newChannel.channel_type}
                onChange={(e) =>
                  setNewChannel({ ...newChannel, channel_type: e.target.value })
                }
                className="w-full"
              >
                {CHANNEL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">
                Config JSON
              </label>
              <textarea
                className="flex min-h-[100px] w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-xs font-mono placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                placeholder='{"bot_token": "...", "chat_id": "..."}'
                value={newChannel.config_json}
                onChange={(e) =>
                  setNewChannel({ ...newChannel, config_json: e.target.value })
                }
              />
            </div>
            {create.error && (
              <p className="text-xs text-red-600">
                错误:{(create.error as Error)?.message}
              </p>
            )}
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => setShowAdd(false)}>
                取消
              </Button>
              <Button
                onClick={() => create.mutate()}
                disabled={
                  create.isPending || !newChannel.book_id || !newChannel.config_json
                }
              >
                保存
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
