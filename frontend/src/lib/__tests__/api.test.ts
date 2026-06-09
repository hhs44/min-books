import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("api.login", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts token to /api/auth/login with credentials: include", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    const { api } = await import("@/lib/api");
    const result = await api.login("test-token");
    expect(result).toEqual({ status: "ok" });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]!;
    expect(url).toContain("/api/auth/login");
    expect(options.method).toBe("POST");
    expect(options.body).toBe(JSON.stringify({ token: "test-token" }));
    expect(options.credentials).toBe("include");
  });

  it("throws APIError on non-ok response", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({ detail: "bad token" }),
    });
    const { api, APIError } = await import("@/lib/api");
    await expect(api.login("bad")).rejects.toBeInstanceOf(APIError);
  });
});

describe("api.me", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/auth/me", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ sub: "admin", scope: ["write"] }),
    });
    const { api } = await import("@/lib/api");
    const me = await api.me();
    expect(me.sub).toBe("admin");
    expect(me.scope).toContain("write");
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]!;
    expect(url).toContain("/api/auth/me");
  });
});

describe("api.listBooks", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/books and returns array", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [{ id: "b1", title: "Test", language: "zh" }],
    });
    const { api } = await import("@/lib/api");
    const books = await api.listBooks();
    expect(Array.isArray(books)).toBe(true);
    expect(books[0]!.id).toBe("b1");
  });
});