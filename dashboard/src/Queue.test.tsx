import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Queue } from "./Queue";
import { idle, Refusal, stubApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const claims = Array.from({ length: 25 }, (_, index) => summary(index + 1));

it("shows every claim with its state and the amount claimed", async () => {
  stubApi({ "GET /api/claims": claims, "GET /api/runs/current": idle });
  render(<Queue />);
  expect(await screen.findAllByText("Waiting")).toHaveLength(26);
  expect(screen.getAllByRole("row")).toHaveLength(26);
  const row = screen.getByRole("row", { name: /CLM-1001/ });
  expect(within(row).getByText("$1,251.00")).toBeDefined();
  expect(within(row).getByText("Trip delay")).toBeDefined();
  expect(
    screen.getByRole("link", { name: "CLM-1001" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1001");
});

it("shows each claim's decision and payout", async () => {
  stubApi({
    "GET /api/claims": [
      summary(1),
      { ...summary(2, "decided"), decision: "approve", payout: 420 },
      { ...summary(3, "decided"), decision: "decline", payout: 0 },
      { ...summary(4, "decided"), decision: "refer", payout: 0 },
    ],
    "GET /api/runs/current": idle,
  });
  render(<Queue />);
  const cells = (id: string) =>
    within(screen.getByRole("row", { name: new RegExp(id) }))
      .getAllByRole("cell")
      .slice(5)
      .map((cell) => cell.textContent);
  await screen.findByText("CLM-1001");
  expect(cells("CLM-1001")).toEqual(["-", "-"]);
  expect(cells("CLM-1002")).toEqual(["Approved", "$420.00"]);
  expect(cells("CLM-1003")).toEqual(["Declined", "$0.00"]);
  expect(cells("CLM-1004")).toEqual(["Referred", "$0.00"]);
});

it("counts the claims in each state", async () => {
  stubApi({
    "GET /api/claims": [
      summary(1),
      summary(2, "in progress"),
      summary(3, "waiting for sign-off"),
      summary(4, "decided"),
      summary(5, "decided"),
    ],
    "GET /api/runs/current": idle,
  });
  render(<Queue />);
  const counts = await screen.findAllByRole("listitem");
  expect(counts.map((item) => item.textContent)).toEqual([
    "1Waiting",
    "1In progress",
    "1Waiting for sign-off",
    "2Decided",
  ]);
});

it("starts a run of the queue", async () => {
  const calls = stubApi({
    "GET /api/claims": claims,
    "GET /api/runs/current": idle,
    "POST /api/runs": { active: true, claim_id: "CLM-1001" },
  });
  render(<Queue />);
  fireEvent.click(await screen.findByRole("button", { name: "Run the queue" }));
  await waitFor(() => {
    expect(calls.some((call) => call.key === "POST /api/runs")).toBe(true);
  });
});

it("says why a run could not start", async () => {
  stubApi({
    "GET /api/claims": claims,
    "GET /api/runs/current": idle,
    "POST /api/runs": new Refusal("A run is already active"),
  });
  render(<Queue />);
  fireEvent.click(await screen.findByRole("button", { name: "Run the queue" }));
  expect(await screen.findByText("A run is already active")).toBeDefined();
});

it("cannot run the queue while a run is active or nothing waits", async () => {
  stubApi({
    "GET /api/claims": claims,
    "GET /api/runs/current": { active: true, claim_id: "CLM-1001" },
  });
  render(<Queue />);
  const button = await screen.findByRole("button", { name: "Run the queue" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  cleanup();
  stubApi({
    "GET /api/claims": [summary(1, "decided")],
    "GET /api/runs/current": idle,
  });
  render(<Queue />);
  const other = await screen.findByRole("button", { name: "Run the queue" });
  expect((other as HTMLButtonElement).disabled).toBe(true);
});

it("refreshes every two seconds while a run is active", async () => {
  vi.useFakeTimers();
  const calls = stubApi({
    "GET /api/claims": [summary(1, "in progress")],
    "GET /api/runs/current": { active: true, claim_id: "CLM-1001" },
  });
  render(<Queue />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(calls).toHaveLength(2);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2100);
  });
  expect(calls).toHaveLength(4);
});

it("does not refresh when nothing is running", async () => {
  vi.useFakeTimers();
  const calls = stubApi({
    "GET /api/claims": claims,
    "GET /api/runs/current": idle,
  });
  render(<Queue />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(calls).toHaveLength(2);
});

it("says when the queue could not be loaded", async () => {
  stubApi({});
  render(<Queue />);
  expect(await screen.findByText("No stub for GET /api/claims")).toBeDefined();
});
