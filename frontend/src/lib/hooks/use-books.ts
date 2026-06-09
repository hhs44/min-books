// frontend/src/lib/hooks/use-books.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useBooks() {
  return useQuery({
    queryKey: ["books"],
    queryFn: () => api.listBooks(),
  });
}

export function useBook(id: string) {
  return useQuery({
    queryKey: ["book", id],
    queryFn: () => api.getBook(id),
    enabled: !!id,
  });
}

export function useChapters(bookId: string) {
  return useQuery({
    queryKey: ["chapters", bookId],
    queryFn: () => api.listChapters(bookId),
    enabled: !!bookId,
  });
}

export function useChapter(bookId: string, num: number) {
  return useQuery({
    queryKey: ["chapter", bookId, num],
    queryFn: () => api.getChapter(bookId, num),
    enabled: !!bookId && num > 0,
  });
}

export function useTruth(bookId: string, fileType: string) {
  return useQuery({
    queryKey: ["truth", bookId, fileType],
    queryFn: () => api.getTruth(bookId, fileType),
    enabled: !!bookId && !!fileType,
  });
}

export function useUpdateTruth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      bookId,
      fileType,
      content,
      expectedVersion,
    }: {
      bookId: string;
      fileType: string;
      content: any;
      expectedVersion?: number;
    }) => api.updateTruth(bookId, fileType, content, expectedVersion),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["truth", vars.bookId, vars.fileType] });
    },
  });
}

export function useSnapshots(bookId: string) {
  return useQuery({
    queryKey: ["snapshots", bookId],
    queryFn: () => api.listSnapshots(bookId),
    enabled: !!bookId,
  });
}
