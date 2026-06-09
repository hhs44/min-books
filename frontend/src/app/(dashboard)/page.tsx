"use client";
import Link from "next/link";
import { useBooks } from "@/lib/hooks/use-books";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BookOpen, Plus, AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function HomePage() {
  const { data: books, isLoading, error } = useBooks();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">我的书籍</h1>
        <Button disabled title="v2-v4 阶段 book-service 端点未实现">
          <Plus className="h-4 w-4 mr-2" /> 新建书籍
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>加载失败:{String((error as Error)?.message ?? error)}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      )}

      {books && books.length === 0 && (
        <Card>
          <CardContent className="text-center py-12 text-gray-500">
            还没有书籍。先用 CLI 创建,然后刷新本页面。
          </CardContent>
        </Card>
      )}

      {books && books.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {books.map((book) => (
            <Link key={book.id} href={`/books/${book.id}`}>
              <Card className="hover:bg-gray-50 transition cursor-pointer h-full">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <BookOpen className="h-5 w-5 text-blue-600" />
                    {book.title}
                  </CardTitle>
                  <CardDescription>
                    {book.genre || "未分类"} · {book.language}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-gray-400 line-clamp-2">
                    ID: {book.id}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
