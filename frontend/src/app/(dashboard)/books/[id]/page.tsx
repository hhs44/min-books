"use client";
import { use } from "react";
import Link from "next/link";
import { useBook, useChapters } from "@/lib/hooks/use-books";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PenTool, FileText, BarChart3 } from "lucide-react";

export default function BookDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: book, isLoading, error } = useBook(id);
  const { data: chapters } = useChapters(id);

  if (isLoading) {
    return <div className="text-gray-500">加载中...</div>;
  }
  if (error || !book) {
    return (
      <div className="text-red-600">书籍不存在或加载失败:{(error as Error)?.message}</div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{book.title}</h1>
          <p className="text-gray-500 mt-1">
            {book.genre || "未分类"} · {book.language}
          </p>
          <p className="text-xs text-gray-400 mt-1">ID: {book.id}</p>
        </div>
        <Link href={`/write?bookId=${id}`}>
          <Button size="lg">
            <PenTool className="h-4 w-4 mr-2" /> 写下一章
          </Button>
        </Link>
      </div>

      <Tabs defaultValue="chapters">
        <TabsList>
          <TabsTrigger value="chapters">章节</TabsTrigger>
          <TabsTrigger value="state">真相文件</TabsTrigger>
          <TabsTrigger value="style">文风</TabsTrigger>
        </TabsList>

        <TabsContent value="chapters" className="space-y-2">
          {chapters && chapters.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-gray-500">暂无章节</CardContent>
            </Card>
          )}
          {chapters?.map((c) => (
            <Link key={c.id} href={`/books/${id}/chapters/${c.chapter_number}`}>
              <Card className="hover:bg-gray-50 cursor-pointer">
                <CardContent className="py-3 flex items-center justify-between">
                  <span>
                    第 {c.chapter_number} 章 {c.title ? `· ${c.title}` : ""}
                  </span>
                  <span className="text-sm text-gray-500">
                    {c.status} · {c.word_count} 字 · v{c.version}
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </TabsContent>

        <TabsContent value="state">
          <Link href={`/state?bookId=${id}`}>
            <Button variant="outline">
              <FileText className="h-4 w-4 mr-2" /> 查看/编辑真相文件
            </Button>
          </Link>
        </TabsContent>

        <TabsContent value="style">
          <Link href={`/style?bookId=${id}`}>
            <Button variant="outline">
              <BarChart3 className="h-4 w-4 mr-2" /> 文风分析
            </Button>
          </Link>
        </TabsContent>
      </Tabs>
    </div>
  );
}
