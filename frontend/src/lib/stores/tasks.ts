// frontend/src/lib/stores/tasks.ts
import { create } from "zustand";

export type PipelineStage =
  | "plan"
  | "compose"
  | "write"
  | "observe"
  | "audit"
  | "settle"
  | "validate"
  | "save";

interface TaskState {
  activeTask: {
    bookId: string;
    runId: string;
    status: "pending" | "running" | "completed" | "failed" | string;
    currentNode?: string;
    streamBuffer: string;
    startedAt?: number;
  } | null;
  startTask: (bookId: string, runId: string) => void;
  setStatus: (status: string) => void;
  setCurrentNode: (node: string) => void;
  appendStream: (text: string) => void;
  finish: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  activeTask: null,
  startTask: (bookId, runId) =>
    set({
      activeTask: {
        bookId,
        runId,
        status: "pending",
        streamBuffer: "",
        startedAt: Date.now(),
      },
    }),
  setStatus: (status) =>
    set((s) =>
      s.activeTask ? { activeTask: { ...s.activeTask, status } } : s,
    ),
  setCurrentNode: (node) =>
    set((s) =>
      s.activeTask ? { activeTask: { ...s.activeTask, currentNode: node } } : s,
    ),
  appendStream: (text) =>
    set((s) =>
      s.activeTask
        ? {
            activeTask: {
              ...s.activeTask,
              streamBuffer: s.activeTask.streamBuffer + text,
            },
          }
        : s,
    ),
  finish: () => set({ activeTask: null }),
}));
