import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest, ensureCsrfToken, setCsrfToken } from "./api";

describe("apiRequest", () => {
  beforeEach(() => {
    setCsrfToken(null);
    vi.restoreAllMocks();
  });

  it("restores the CSRF session and protects mutations", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "secure-token" }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "ok" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    await apiRequest("/conversations", { method: "POST", body: JSON.stringify({ title: "Test" }) });
    expect(fetchMock.mock.calls[1][1].credentials).toBe("include");
    expect(fetchMock.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("secure-token");
  });

  it("surfaces backend failures and emits unauthorized events", async () => {
    setCsrfToken("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "Session expired" }), { status: 401, headers: { "Content-Type": "application/json" } }));
    const listener = vi.fn();
    window.addEventListener("internassist:unauthorized", listener);
    await expect(apiRequest("/documents")).rejects.toThrow("Session expired");
    expect(listener).toHaveBeenCalledOnce();
  });

  it("deduplicates concurrent CSRF session bootstrap", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ csrf_token: "one-token" }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const [first, second] = await Promise.all([ensureCsrfToken(), ensureCsrfToken()]);
    expect(first).toBe("one-token");
    expect(second).toBe("one-token");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
