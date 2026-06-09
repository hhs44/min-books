"use client";
import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useTruth, useUpdateTruth, useBook } from "@/lib/hooks/use-books";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

const FILE_TYPES = [
  "current_state",
  "character_matrix",
  "pending_hooks",
  "chapter_summaries",
  "subplot_board",
  "emotional_arcs",
  "particle_ledger",
] as const;

type FileType = (typeof FILE_TYPES)[number];

const LABELS: Record<FileType, string> = {
  current_state: "当前状态",
  character_matrix: "角色矩阵",
  pending_hooks: "未结伏笔",
  chapter_summaries: "章节摘要",
  subplot_board: "支线板",
  emotional_arcs: "情感曲线",
  particle_ledger: "粒子账本",
};

export default function StatePage() {
  return (
    <Suspense fallback={<div className="text-gray-500">加载...</div>}>
      <StatePageInner />
    </Suspense>
  );
}

function StatePageInner() {
  const sp = useSearchParams();
  const bookId = sp.get("bookId") || "";
  const [activeType, setActiveType] = useState<FileType>(FILE_TYPES[0]);
  const { data: book } = useBook(bookId);
  const { data: truth, isLoading } = useTruth(bookId, activeType);
  const update = useUpdateTruth();

  const [editContent, setEditContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    if (truth) {
      setEditContent(JSON.stringify(truth.content, null, 2));
      setJsonError(null);
    }
  }, [truth]);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold text-gray-900">真相文件</h1>
      {book && <p className="text-gray-500">{book.title}</p>}

      {!bookId && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>请从书籍详情页进入,或在 URL 添加 ?bookId=...</AlertDescription>
        </Alert>
      )}

      <div>
        <Input
          placeholder="Book ID"
          value={bookId}
          onChange={() => {}}
          readOnly
          className="max-w-md"
        />
      </div>

      <Tabs value={activeType} onValueChange={(v) => setActiveType(v as FileType)}>
        <TabsList className="flex-wrap h-auto">
          {FILE_TYPES.map((t) => (
            <TabsTrigger key={t} value={t}>
              {LABELS[t]}
            </TabsTrigger>
          ))}
        </TabsList>
        {FILE_TYPES.map((t) => (
          <TabsContent key={t} value={t}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{LABELS[t]}</span>
                  {truth && <Badge variant="outline">v{truth.version}</Badge>}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading && <div className="text-gray-500 text-sm">加载中...</div>}
                {!editing ? (
                  <>
                    <pre className="bg-gray-50 p-4 rounded text-xs overflow-auto max-h-96 font-mono">
                      {JSON.stringify(truth?.content, null, 2)}
                    </pre>
                    <Button
                      onClick={() => setEditing(true)}
                      className="mt-3"
                      size="sm"
                      disabled={!truth}
                    >
                      编辑
                    </Button>
                  </>
                ) : (
                  <>
                    <Textarea
                      value={editContent}
                      onChange={(e) => {
                        setEditContent(e.target.value);
                        try {
                          JSON.parse(e.target.value);
                          setJsonError(null);
                        } catch (err) {
                          setJsonError((err as Error).message);
                        }
                      }}
                      rows={20}
                      className="font-mono text-xs"
                    />
                    {jsonError && (
                      <p className="text-xs text-red-600 mt-1">JSON 解析错误:{jsonError}</p>
                    )}
                    {update.error && (
                      <Alert variant="destructive" className="mt-2">
                        <AlertDescription>
                          保存失败:{(update.error as Error)?.message}
                        </AlertDescription>
                      </Alert>
                    )}
                    <div className="flex gap-2 mt-3">
                      <Button
                        onClick={() => {
                          try {
                            const content = JSON.parse(editContent);
                            update.mutate(
                              {
                                bookId,
                                fileType: t,
                                content,
                                expectedVersion: truth?.version,
                              },
                              {
                                onSuccess: () => setEditing(false),
                              },
                            );
                          } catch {
                            setJsonError("JSON 解析失败");
                          }
                        }}
                        disabled={update.isPending || !!jsonError}
                      >
                        保存
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setEditing(false);
                          if (truth)
                            setEditContent(JSON.stringify(truth.content, null, 2));
                        }}
                      >
                        取消
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
