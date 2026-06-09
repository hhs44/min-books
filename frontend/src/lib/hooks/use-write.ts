// frontend/src/lib/hooks/use-write.ts
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SSEClient } from "@/lib/sse";
import { useTaskStore } from "@/lib/stores/tasks";

const GATEWAY =
  process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";

export function useWriteNext() {
  const startTask = useTaskStore((s) => s.startTask);
  const setStatus = useTaskStore((s) => s.setStatus);
  const setCurrentNode = useTaskStore((s) => s.setCurrentNode);
  const appendStream = useTaskStore((s) => s.appendStream);
  const finish = useTaskStore((s) => s.finish);

  return useMutation({
    mutationFn: async (params: {
      bookId: string;
      chapterNumber: number;
      currentFocus: string;
      bookSettings: any;
    }) => {
      const { bookId, chapterNumber, currentFocus, bookSettings } = params;
      // 1. Start the pipeline
      const { pipeline_run_id } = await api.writeNext(bookId, {
        chapter_number: chapterNumber,
        current_focus: currentFocus,
        book_settings: bookSettings,
      });
      startTask(bookId, pipeline_run_id);
      setStatus("running");

      // 2. Open SSE to stream progress
      const sse = new SSEClient(
        `${GATEWAY}/api/books/${bookId}/write/stream/${pipeline_run_id}`,
      );
      sse.connect({
        onPipelineProgress: ({ stage }) => {
          setCurrentNode(stage);
        },
        onStreamText: ({ text, done }) => {
          if (!done) appendStream(text);
        },
        onAuditResult: ({ issues, severity }) => {
          console.log(`Audit: ${issues} issues (${severity})`);
        },
        onTaskCompleted: ({ word_count }) => {
          console.log(`Task completed: ${word_count} words`);
          setStatus("completed");
          sse.close();
        },
        onError: (err) => {
          console.error("SSE error", err);
          setStatus("failed");
        },
        onOpen: () => {
          // connection established
        },
      });

      return { pipeline_run_id };
    },
    onSettled: () => {
      // Keep the active task visible for 3s so the user sees the final state
      setTimeout(finish, 3000);
    },
  });
}
