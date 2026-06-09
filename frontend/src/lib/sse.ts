// frontend/src/lib/sse.ts
// SSE client (EventSource-based) for live pipeline streaming

export interface SSECallbacks {
  onPipelineProgress?: (data: {
    stage: string;
    progress: number;
    message?: string;
  }) => void;
  onStreamText?: (data: { text: string; done: boolean }) => void;
  onAuditResult?: (data: { issues: number; severity: string }) => void;
  onTaskCompleted?: (data: {
    task_id: string;
    word_count: number;
    chapter_number?: number;
  }) => void;
  onError?: (err: Event) => void;
  onOpen?: () => void;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;

  constructor(url: string) {
    this.url = url;
  }

  connect(callbacks: SSECallbacks): void {
    if (typeof window === "undefined") return; // SSR guard
    this.eventSource = new EventSource(this.url, { withCredentials: true });

    if (callbacks.onOpen) {
      this.eventSource.addEventListener("open", () => callbacks.onOpen?.());
    }

    this.eventSource.addEventListener("pipeline_progress", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        callbacks.onPipelineProgress?.(data);
      } catch (err) {
        console.error("Failed to parse pipeline_progress", err);
      }
    });

    this.eventSource.addEventListener("stream_text", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        callbacks.onStreamText?.(data);
      } catch (err) {
        console.error("Failed to parse stream_text", err);
      }
    });

    this.eventSource.addEventListener("audit_result", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        callbacks.onAuditResult?.(data);
      } catch (err) {
        console.error("Failed to parse audit_result", err);
      }
    });

    this.eventSource.addEventListener("task_completed", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        callbacks.onTaskCompleted?.(data);
      } catch (err) {
        console.error("Failed to parse task_completed", err);
      }
    });

    this.eventSource.addEventListener("done", () => {
      this.close();
    });

    this.eventSource.addEventListener("error", (e) => {
      callbacks.onError?.(e);
      // EventSource auto-reconnects unless we close
    });
  }

  close(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
