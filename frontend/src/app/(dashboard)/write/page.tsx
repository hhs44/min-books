"use client";
import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useWriteNext } from "@/lib/hooks/use-write";
import { useTaskStore } from "@/lib/stores/tasks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { PenTool, Loader2, AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

const STAGES = [
  "plan",
  "compose",
  "write",
  "observe",
  "audit",
  "settle",
  "validate",
  "save",
];

export default function WritePage() {
  return (
    <Suspense fallback={<div className="text-gray-500">加载...</div>}>
      <WritePageInner />
    </Suspense>
  );
}

function WritePageInner() {
  const searchParams = useSearchParams();
  const bookId = searchParams.get("bookId") || "";
  const [chapterNumber, setChapterNumber] = useState(1);
  const [currentFocus, setCurrentFocus] = useState("");

  const writeMutation = useWriteNext();
  const activeTask = useTaskStore((s) => s.activeTask);

  const currentStageIdx = activeTask?.currentNode
    ? STAGES.indexOf(activeTask.currentNode)
    : -1;

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      // SSEClient closes itself on completion
    };
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">写作工作台</h1>

      <Card>
        <CardHeader>
          <CardTitle>触发新章节</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium block mb-1.5">章节号</label>
              <Input
                type="number"
                min={1}
                value={chapterNumber}
                onChange={(e) => setChapterNumber(parseInt(e.target.value || "1", 10))}
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">书籍 ID</label>
              <Input value={bookId} readOnly className="bg-gray-50" placeholder="从书籍详情页进入" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1.5">作者意图 / 当前焦点</label>
            <Textarea
              placeholder="描述本章你想表达的内容..."
              value={currentFocus}
              onChange={(e) => setCurrentFocus(e.target.value)}
              rows={3}
            />
          </div>
          {writeMutation.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {(writeMutation.error as Error)?.message ?? "请求失败"}
              </AlertDescription>
            </Alert>
          )}
          <Button
            onClick={() =>
              writeMutation.mutate({
                bookId,
                chapterNumber,
                currentFocus,
                bookSettings: {},
              })
            }
            disabled={!bookId || !currentFocus || writeMutation.isPending}
            size="lg"
            className="w-full"
          >
            {writeMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" /> 写作中...
              </>
            ) : (
              <>
                <PenTool className="h-4 w-4 mr-2" /> 开始写
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Progress */}
      {activeTask && (
        <Card>
          <CardHeader>
            <CardTitle>实时进度</CardTitle>
            <div className="flex items-center gap-2 mt-2">
              <Badge
                variant={
                  activeTask.status === "completed"
                    ? "default"
                    : activeTask.status === "failed"
                      ? "destructive"
                      : "secondary"
                }
              >
                {activeTask.status}
              </Badge>
              {activeTask.currentNode && (
                <span className="text-sm text-gray-500">当前:{activeTask.currentNode}</span>
              )}
              <span className="text-xs text-gray-400">run {activeTask.runId.slice(0, 8)}</span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-8 gap-1">
              {STAGES.map((stage, i) => (
                <div
                  key={stage}
                  className={`h-2 rounded ${i <= currentStageIdx ? "bg-blue-600" : "bg-gray-200"}`}
                  title={stage}
                />
              ))}
            </div>
            <Progress
              value={((currentStageIdx + 1) / STAGES.length) * 100}
            />
            <div className="text-xs text-gray-500 flex justify-between">
              {STAGES.map((s, i) => (
                <span key={s} className={i === currentStageIdx ? "text-blue-600 font-medium" : ""}>
                  {s}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stream output */}
      {activeTask && activeTask.streamBuffer && (
        <Card>
          <CardHeader>
            <CardTitle>正文流(实时)</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm font-serif leading-relaxed">
              {activeTask.streamBuffer}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
