import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiRequest, ensureCsrfToken } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  ensureCsrfToken: vi.fn(() => Promise.resolve("token")),
}));
vi.mock("../lib/api", () => ({
  apiRequest,
  ensureCsrfToken,
  setCsrfToken: vi.fn(),
}));

import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { currentUser, loading, login } = useAuth();
  return <div><span>{loading ? "loading" : currentUser?.email || "guest"}</span><button onClick={async () => { const result = await login("x@example.com", "bad"); document.body.dataset.result = result.error; }}>login</button></div>;
}

describe("AuthProvider", () => {
  beforeEach(() => { apiRequest.mockReset(); ensureCsrfToken.mockClear(); delete document.body.dataset.result; });

  it("restores an authenticated session", async () => {
    apiRequest.mockResolvedValueOnce({ user: { email: "student@example.com", role: "student" } });
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(await screen.findByText("student@example.com")).toBeInTheDocument();
  });

  it("settles as guest and reports login failures", async () => {
    apiRequest.mockRejectedValueOnce(new Error("Not authenticated")).mockRejectedValueOnce(new Error("Invalid credentials"));
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(await screen.findByText("guest")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "login" }));
    await waitFor(() => expect(document.body.dataset.result).toBe("Invalid credentials"));
  });
});
