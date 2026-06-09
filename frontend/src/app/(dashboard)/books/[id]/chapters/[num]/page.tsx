"use client";
import { use } from "react";
import { useChapter, useBook } from "@/lib/hooks/use-books";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function ChapterPage({
  params,
}: {
  params: Promise<{ id: string; num: string }>;
}) {
  const { id, num } = use(params);
  const numN = parseInt(num, 10);
  const { data: book } = useBook(id);
  const { data: chapter, isLoading } = useChapter(id, numN);

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {book && (
        <p className="text-sm text-gray-500">
          {book.title} / 第 {numN} 章
        </p>
      )}
      <h1 className="text-3xl font-bold text-gray-900">
        第 {numN} 章 {chapter?.title ? `· ${chapter.title}` : ""}
      </h1>
      {chapter && (
        <div className="flex items-center gap-2">
          <Badge variant="outline">{chapter.status}</Badge>
          <span className="text-sm text-gray-500">
            {chapter.word_count} 字 · v{chapter.version}
          </span>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>正文</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-96" />}
          {chapter?.content ? (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap font-serif leading-relaxed">
              {chapter.content}
            </div>
          ) : (
            !isLoading && <p className="text-gray-500">无内容</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
