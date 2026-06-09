// frontend/src/lib/api.ts
// Frontend API client: all requests go through the gateway
const GATEWAY =
  process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";

export class APIError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: any,
  ) {
    super(`${status} ${statusText}: ${JSON.stringify(body)}`);
    this.name = "APIError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${GATEWAY}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new APIError(res.status, res.statusText, body);
  }
  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function requestBlob(
  path: string,
  options: RequestInit = {},
): Promise<Blob> {
  const res = await fetch(`${GATEWAY}${path}`, {
    ...options,
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new APIError(res.status, res.statusText, body);
  }
  return res.blob();
}

export const api = {
  // ---------- Auth ----------
  login: (token: string) =>
    request<{ status: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  logout: () =>
    request<{ status: string }>("/api/auth/logout", { method: "POST" }),
  me: () => request<{ sub: string; scope: string[] }>("/api/auth/me"),

  // ---------- Books ----------
  listBooks: () => request<Book[]>("/api/books"),
  getBook: (id: string) => request<Book>(`/api/books/${id}`),
  createBook: (body: { title: string; genre?: string; language?: string }) =>
    request<Book>("/api/books", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateBook: (id: string, body: Partial<Book>) =>
    request<Book>(`/api/books/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteBook: (id: string) =>
    request<{ status: string }>(`/api/books/${id}`, { method: "DELETE" }),

  // ---------- Chapters ----------
  listChapters: (bookId: string) =>
    request<Chapter[]>(`/api/books/${bookId}/chapters`),
  getChapter: (bookId: string, num: number) =>
    request<Chapter>(`/api/books/${bookId}/chapters/${num}`),
  importChapter: (
    bookId: string,
    body: { format: string; content: string },
  ) =>
    request<{ status: string }>(`/api/books/${bookId}/chapters/import`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  exportBook: (bookId: string, format: "txt" | "md" | "epub") =>
    requestBlob(`/api/books/${bookId}/export?format=${format}`),

  // ---------- Write Pipeline ----------
  writeNext: (
    bookId: string,
    body: {
      chapter_number: number;
      current_focus: string;
      book_settings: any;
    },
  ) =>
    request<{ pipeline_run_id: string; status: string }>(
      `/api/books/${bookId}/write/next`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  getTaskStatus: (bookId: string, taskId: string) =>
    request<TaskStatus>(`/api/books/${bookId}/write/tasks/${taskId}`),

  // ---------- State ----------
  getTruth: (bookId: string, fileType: string) =>
    request<{ content: any; version: number }>(
      `/api/books/${bookId}/state/${fileType}`,
    ),
  updateTruth: (
    bookId: string,
    fileType: string,
    content: any,
    expectedVersion?: number,
  ) =>
    request<{ status: string; version: number }>(
      `/api/books/${bookId}/state/${fileType}`,
      {
        method: "PUT",
        body: JSON.stringify({ content, expected_version: expectedVersion }),
      },
    ),
  listSnapshots: (bookId: string) =>
    request<
      Array<{ id: string; chapter_number: number; created_at: string }>
    >(`/api/books/${bookId}/state/snapshots`),

  // ---------- Style ----------
  analyzeStyle: (bookId: string) =>
    request<{ style_summary: any }>(`/api/books/${bookId}/style/analyze`, {
      method: "POST",
    }),
  getFingerprint: (bookId: string) =>
    request<{ fingerprint: any }>(`/api/books/${bookId}/style/fingerprint`),

  // ---------- LLM ----------
  listProviders: () => request<string[]>("/api/llm/providers"),
  listModels: () =>
    request<
      Array<{
        provider: string;
        model: string;
        input_cost: number;
        output_cost: number;
      }>
    >("/api/llm/models"),
  testConnection: (body: {
    provider: string;
    model: string;
    api_key?: string;
    base_url?: string;
  }) =>
    request<{
      status: string;
      response?: string;
      latency_ms?: number;
      error?: string;
    }>("/api/llm/test", { method: "POST", body: JSON.stringify(body) }),

  // ---------- Config ----------
  getConfig: () => request<Record<string, any>>("/api/config"),
  updateConfig: (key: string, value: any) =>
    request<{ status: string }>("/api/config", {
      method: "PUT",
      body: JSON.stringify({ config_key: key, config_value: value }),
    }),

  // ---------- Doctor ----------
  doctor: () =>
    request<{
      status: string;
      services: Array<{ name: string; status: string; url: string }>;
    }>("/api/doctor"),

  // ---------- Notifications ----------
  listChannels: (bookId?: string) => {
    const q = bookId ? `?book_id=${bookId}` : "";
    return request<Channel[]>(`/api/notifications/channels${q}`);
  },
  createChannel: (body: {
    book_id: string;
    channel_type: string;
    config_json: any;
  }) =>
    request<{ id: string }>("/api/notifications/channels", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateChannel: (id: string, body: { config_json?: any; enabled?: boolean }) =>
    request<{ status: string }>(`/api/notifications/channels/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteChannel: (id: string) =>
    request<{ status: string }>(`/api/notifications/channels/${id}`, {
      method: "DELETE",
    }),
  testChannel: (id: string) =>
    request<{ status: string }>(`/api/notifications/test/${id}`, {
      method: "POST",
    }),

  // ---------- Cost ----------
  getCostSummary: () => request<CostSummary>("/api/cost/summary"),
  getDailyCosts: (days: number = 30) =>
    request<Array<{ day: string; cost: number; calls: number }>>(
      `/api/cost/daily?days=${days}`,
    ),
  getCostByBook: () =>
    request<Array<{ book_id: string; title: string; cost: number }>>(
      "/api/cost/by-book",
    ),
  getRecentCalls: (limit: number = 50) =>
    request<any[]>(`/api/cost/recent-calls?limit=${limit}`),
  getCostThresholds: () => request<CostThresholds>("/api/cost/thresholds"),
  updateCostThresholds: (body: CostThresholds) =>
    request<{ status: string }>("/api/cost/thresholds", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  // ---------- Agents (v4) ----------
  listAgents: () =>
    request<
      Array<{
        agent_id: string;
        agent_type: string;
        status: string;
        last_heartbeat?: string;
        current_task?: string;
      }>
    >("/api/agents"),
};

// ---------- Types ----------
export interface Book {
  id: string;
  title: string;
  genre?: string;
  language: string;
  config_json: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface Chapter {
  id: string;
  book_id: string;
  chapter_number: number;
  title?: string;
  content?: string;
  status: string;
  word_count: number;
  version: number;
  created_at?: string;
  updated_at?: string;
}

export interface TaskStatus {
  pipeline_run_id: string;
  status: string;
  checkpoints: Record<string, any>;
  error?: any;
  started_at?: string;
  completed_at?: string;
}

export interface Channel {
  id: string;
  book_id: string;
  channel_type: string;
  config_summary: Record<string, any>;
  enabled: boolean;
}

export interface CostSummary {
  today: number;
  this_week: number;
  this_month: number;
  this_year: number;
}

export interface CostThresholds {
  daily_usd: number;
  monthly_usd: number;
  per_book_usd: number;
  spike_multiplier: number;
}
