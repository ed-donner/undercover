import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockApi } from "./mockApi";
import { Queue } from "./Queue";
import type { ClaimSummary, Run } from "./types";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function claim(
  id: string,
  overrides: Partial<ClaimSummary> = {},
): ClaimSummary {
  return {
    claim_id: id,
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    summary: "Flight canceled",
    amount_claimed: 1250,
    submitted_on: "2026-06-24",
    status: "waiting",
    decision: null,
    payout: null,
    ...overrides,
  };
}

const CLAIMS = [
  claim("CLM-1001"),
  claim("CLM-1002", { status: "in_progress" }),
  claim("CLM-1003", {
    status: "waiting_for_sign_off",
    decision: "approve",
    payout: 1250,
  }),
  claim("CLM-1004", { status: "decided", decision: "decline", payout: 0 }),
  claim("CLM-1005", { status: "decided", decision: "refer", payout: 0 }),
];

it("lists the claims with their status, amounts and decisions", async () => {
  mockApi({ "GET /api/claims": CLAIMS });
  render(<Queue />);
  expect(await screen.findAllByRole("row")).toHaveLength(6);
  const row = screen.getByRole("row", { name: /CLM-1003/ });
  expect(within(row).getByText("Waiting for sign-off")).toBeDefined();
  expect(within(row).getByText("Approved, $1,250.00")).toBeDefined();
  expect(within(row).getByText("Trip delay")).toBeDefined();
  expect(
    within(row).getByRole("link", { name: "CLM-1003" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1003");
  expect(screen.getByText("Declined")).toBeDefined();
  expect(screen.getByText("Referred")).toBeDefined();
});

it("counts each status and filters by it", async () => {
  mockApi({ "GET /api/claims": CLAIMS });
  render(<Queue />);
  const decided = await screen.findByRole("button", { name: "Decided 2" });
  expect(screen.getByRole("button", { name: "All 5" })).toBeDefined();
  expect(screen.getByRole("button", { name: "Waiting 1" })).toBeDefined();
  expect(screen.getByRole("button", { name: "In progress 1" })).toBeDefined();
  fireEvent.click(decided);
  expect(screen.getAllByRole("row")).toHaveLength(3);
  expect(screen.queryByText("CLM-1001")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "All 5" }));
  expect(screen.getAllByRole("row")).toHaveLength(6);
});

it("says so when no claim has the status", async () => {
  mockApi({ "GET /api/claims": [claim("CLM-1001")] });
  render(<Queue />);
  fireEvent.click(await screen.findByRole("button", { name: "Decided 0" }));
  expect(screen.getByText("No claims with this status.")).toBeDefined();
});

it("runs the agent on one claim and then reloads", async () => {
  const fetchMock = mockApi({
    "GET /api/claims": [claim("CLM-1001")],
    "POST /api/claims/CLM-1001/run": {},
  });
  render(<Queue />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(fetchMock).toHaveBeenCalledWith("/api/claims/CLM-1001/run", {
    method: "POST",
  });
  await vi.waitFor(() => {
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/claims"),
    ).toHaveLength(2);
  });
});

it("runs the agent on all waiting claims", async () => {
  const fetchMock = mockApi({
    "GET /api/claims": CLAIMS,
    "POST /api/queue/run": { run_id: 1 },
  });
  render(<Queue />);
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Run agent on all waiting claims",
    }),
  );
  expect(fetchMock).toHaveBeenCalledWith("/api/queue/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit: 1 }),
  });
});

const RUN: Run = {
  run_id: 1,
  limit: 5,
  status: "running",
  summary: "",
  started_at: "2026-10-19T09:00:00+00:00",
  finished_at: null,
  todos: [{ text: "CLM-1001, trip delay", status: "in_progress" }],
};

it("shows no run panel before the first run", async () => {
  mockApi({ "GET /api/claims": CLAIMS, "GET /api/runs/latest": null });
  render(<Queue />);
  await screen.findByText("CLM-1001", { selector: "a" });
  expect(screen.queryByText("Current run")).toBeNull();
});

it("shows the latest run and its to-do list", async () => {
  mockApi({ "GET /api/claims": CLAIMS, "GET /api/runs/latest": RUN });
  render(<Queue />);
  expect(await screen.findByText("Current run")).toBeDefined();
  expect(screen.getByText("CLM-1001, trip delay")).toBeDefined();
});

it("does not start another run while one is running", async () => {
  mockApi({ "GET /api/claims": CLAIMS, "GET /api/runs/latest": RUN });
  render(<Queue />);
  await screen.findByText("Current run");
  for (const name of ["Run agent on all waiting claims", "Run trial"]) {
    expect(screen.getByRole("button", { name }).hasAttribute("disabled")).toBe(
      true,
    );
  }
});

it("runs a trial of the number of claims chosen", async () => {
  const fetchMock = mockApi({
    "GET /api/claims": CLAIMS,
    "POST /api/queue/run": { run_id: 1 },
  });
  render(<Queue />);
  const box = await screen.findByLabelText("Claims in a trial");
  expect((box as HTMLInputElement).value).toBe("5");
  fireEvent.change(box, { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Run trial" }));
  expect(fetchMock).toHaveBeenCalledWith("/api/queue/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit: 2 }),
  });
});

it("counts the claims that need a handler", async () => {
  mockApi({
    "GET /api/claims": [claim("CLM-1006", { status: "needs_handler" })],
  });
  render(<Queue />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Needs a handler 1" }),
  );
  const row = screen.getByRole("row", { name: /CLM-1006/ });
  expect(within(row).getByText("Needs a handler").className).toContain(
    "chip-needs_handler",
  );
});

it("has no run buttons when nothing is waiting", async () => {
  mockApi({
    "GET /api/claims": [
      claim("CLM-1004", { status: "decided", decision: "decline", payout: 0 }),
    ],
  });
  render(<Queue />);
  await screen.findByText("CLM-1004");
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
  const all = screen.getByRole("button", {
    name: "Run agent on all waiting claims",
  });
  expect(all.hasAttribute("disabled")).toBe(true);
});

it("tells the handler when the agent could not be started", async () => {
  mockApi({ "GET /api/claims": [claim("CLM-1001")] });
  render(<Queue />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The agent could not be started.",
  );
});

it("shows an error when the queue cannot be loaded", async () => {
  mockApi({});
  render(<Queue />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The queue could not be loaded.",
  );
});

it("refreshes every few seconds", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes = { "GET /api/claims": [claim("CLM-1001")] };
  mockApi(routes);
  render(<Queue />);
  await screen.findByRole("button", { name: "Waiting 1" });
  routes["GET /api/claims"] = [claim("CLM-1001", { status: "in_progress" })];
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(
    await screen.findByRole("button", { name: "In progress 1" }),
  ).toBeDefined();
});
