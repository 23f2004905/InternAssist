import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const { apiRequest } = vi.hoisted(() => ({ apiRequest: vi.fn() }));
vi.mock("../lib/api", () => ({ apiRequest }));
vi.mock("../components/Navbar", () => ({ default: () => <nav>Navigation</nav> }));

import AskAssistant from "./AskAssistant";

beforeEach(() => apiRequest.mockReset());

it("creates one conversation and submits the first message exactly once", async () => {
  apiRequest
    .mockResolvedValueOnce({ conversation: { id: 7, title: "First question" } })
    .mockResolvedValueOnce({ conversation: { id: 7, title: "First question" }, messages: [{ id: 1, role: "user", content: "First question", citations: [] }, { id: 2, role: "assistant", content: "Answer", citations: [] }] })
    .mockResolvedValueOnce({ conversation: { id: 7, title: "First question" }, messages: [] });
  render(<MemoryRouter initialEntries={["/assistant"]}><Routes><Route path="/assistant" element={<AskAssistant />} /><Route path="/conversations/:conversationId" element={<AskAssistant />} /></Routes></MemoryRouter>);
  const input = screen.getByLabelText("Ask a question");
  await userEvent.type(input, "First question");
  const submit = screen.getByRole("button", { name: "Ask →" });
  await Promise.all([userEvent.click(submit), userEvent.click(submit)]);
  await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/conversations/7/ask", expect.any(Object)));
  expect(apiRequest.mock.calls.filter(([path]) => path === "/conversations")).toHaveLength(1);
  expect(apiRequest.mock.calls.filter(([path]) => path === "/conversations/7/ask")).toHaveLength(1);
});

it("shows persisted citations when a conversation is reopened", async () => {
  apiRequest.mockResolvedValueOnce({ conversation: { id: 8, title: "Policy" }, messages: [{ id: 2, role: "assistant", content: "Answer", citations: [{ document_id: 3, document_name: "policy.pdf", page_number: 4 }] }] });
  render(<MemoryRouter initialEntries={["/conversations/8"]}><Routes><Route path="/conversations/:conversationId" element={<AskAssistant />} /></Routes></MemoryRouter>);
  expect(await screen.findByText("policy.pdf")).toBeInTheDocument();
  expect(screen.getByText(/Page 4/)).toBeInTheDocument();
});

it("prefills a question handed off from a dashboard", async () => {
  render(
    <MemoryRouter initialEntries={[{ pathname: "/assistant", state: { question: "What is the internship deadline?" } }]}>
      <Routes><Route path="/assistant" element={<AskAssistant />} /></Routes>
    </MemoryRouter>,
  );
  expect(screen.getByLabelText("Ask a question")).toHaveValue("What is the internship deadline?");
});
