import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

const claims = [
  {
    claim_id: "CLM-1001",
    claim_type: "trip_cancellation",
    summary: "Flight cancelled",
    amount_claimed: 1250,
    status: "decided",
    attempts: 1,
    decision: "approve",
    payout: 1000,
  },
  {
    claim_id: "CLM-1002",
    claim_type: "baggage",
    summary: "Lost bag",
    amount_claimed: 300,
    status: "waiting",
    attempts: 0,
    decision: null,
    payout: null,
  },
];

const run = {
  run_id: 1,
  cap: 5,
  claim_id: null,
  status: "running",
  summary: "Two claims decided.",
  todos: [
    { text: "Work CLM-1002", state: "todo", claim_id: "CLM-1002" },
    { text: "Work CLM-1001", state: "done", claim_id: "CLM-1001" },
  ],
};

const detail = {
  ...claims[0],
  decision: {
    decision: "approve",
    payout: 1000,
    section: "Wording 3",
    reason: "Covered.",
  },
  payment: { amount: 1000, paid_at: "now" },
  steps: [{ tool: "get_claim", summary: "read the claim", at: "t1" }],
  reads: [{ document: "manual", number: 4, title: "Deciding a claim" }],
};

function serve(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string) =>
      path in routes
        ? Promise.resolve(new Response(JSON.stringify(routes[path])))
        : Promise.resolve(new Response("{}", { status: 500 })),
    ),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

it("shows that the backend is up and the queue with its to-do list", async () => {
  serve({
    "/api/health": {},
    "/api/claims": claims,
    "/api/runs/current": run,
  });
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
  expect(await screen.findByText("Work CLM-1002")).toBeDefined();
  expect(screen.getByText("Two claims decided.")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  const items = screen.getAllByRole("listitem").map((li) => li.textContent);
  expect(items[0]).toContain("Work CLM-1002");
  expect(items[1]).toContain("Work CLM-1001");
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("shows the queue when there is no run", async () => {
  serve({ "/api/health": {}, "/api/claims": [], "/api/runs/current": null });
  render(<App />);
  expect(await screen.findByText("No run yet.")).toBeDefined();
});

it("shows an empty to-do list", async () => {
  serve({
    "/api/health": {},
    "/api/claims": [],
    "/api/runs/current": { ...run, summary: null, todos: [] },
  });
  render(<App />);
  expect(
    await screen.findByText("The agent has not written a to-do list yet."),
  ).toBeDefined();
});

it("shows a claim with its steps and the sections read", async () => {
  window.location.hash = "#/claims/CLM-1001";
  serve({ "/api/health": {}, "/api/claims/CLM-1001": detail });
  render(<App />);
  expect(await screen.findByText("Sections read")).toBeDefined();
  expect(screen.getByText(/Manual section 4: Deciding a claim/)).toBeDefined();
  expect(screen.getByText("get_claim")).toBeDefined();
  expect(screen.getByText(/Covered\./)).toBeDefined();
});

it("shows a claim that is not decided", async () => {
  window.location.hash = "#/claims/CLM-1002";
  serve({
    "/api/health": {},
    "/api/claims/CLM-1002": {
      ...claims[1],
      decision: null,
      payment: null,
      steps: [],
      reads: [],
    },
  });
  render(<App />);
  expect(await screen.findByText("No sections read.")).toBeDefined();
  expect(screen.getByText("No steps recorded.")).toBeDefined();
});

it("says when a claim cannot be loaded", async () => {
  window.location.hash = "#/claims/CLM-9999";
  serve({ "/api/health": {} });
  render(<App />);
  expect(await screen.findByText(/CLM-9999 could not be loaded/)).toBeDefined();
});

it("shows both instructions", async () => {
  window.location.hash = "#/instructions";
  serve({
    "/api/health": {},
    "/api/instructions": {
      queue_runner: "Run the queue.",
      claim: "Decide it.",
    },
  });
  render(<App />);
  expect(await screen.findByText("Run the queue.")).toBeDefined();
  expect(screen.getByText("Decide it.")).toBeDefined();
});

it("says when the instructions cannot be loaded", async () => {
  window.location.hash = "#/instructions";
  serve({ "/api/health": {} });
  render(<App />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
