import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { QueuePage } from "./QueuePage";
import { Failure, queueEntry, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("lists each claim with where it stands", async () => {
  stubApi({
    "GET /api/claims": [
      queueEntry(),
      queueEntry({
        claim_id: "CLM-1002",
        customer_name: "Sam Ortiz",
        claim_type: "baggage",
        status: "decided",
        decision: "approve",
        payout: 420,
        paid_amount: 420,
      }),
      queueEntry({
        claim_id: "CLM-1003",
        status: "decided",
        decision: "decline",
        payout: 0,
      }),
    ],
  });
  render(<QueuePage />);
  const first = await screen.findByRole("row", { name: /CLM-1001/ });
  expect(within(first).getByText("Maya Patel")).toBeDefined();
  expect(within(first).getByText("Trip delay")).toBeDefined();
  expect(within(first).getByText("Jun 24, 2026")).toBeDefined();
  expect(within(first).getByText("$1,250.00")).toBeDefined();
  expect(within(first).getByText("Waiting")).toBeDefined();
  expect(
    within(first).getByRole("link", { name: "CLM-1001" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1001");
  const second = screen.getByRole("row", { name: /CLM-1002/ });
  expect(within(second).getByText("Approved")).toBeDefined();
  expect(within(second).getByText("$420.00")).toBeDefined();
  const third = screen.getByRole("row", { name: /CLM-1003/ });
  expect(within(third).getByText("Declined")).toBeDefined();
  expect(within(third).queryByText("$0.00")).toBeNull();
});

it("counts the claims in each status", async () => {
  stubApi({
    "GET /api/claims": [
      queueEntry(),
      queueEntry({ claim_id: "CLM-1002" }),
      queueEntry({ claim_id: "CLM-1003", status: "waiting_for_sign_off" }),
      queueEntry({ claim_id: "CLM-1004", status: "left_for_handler" }),
    ],
  });
  render(<QueuePage />);
  const counts = await screen.findByRole("region", {
    name: "Claims by status",
  });
  expect(counts.textContent).toBe(
    "2Waiting0In progress1Waiting for sign-off0Decided1Left for a handler",
  );
  const left = screen.getByRole("row", { name: /CLM-1004/ });
  expect(within(left).getByText("Left for a handler").className).toContain(
    "status-left_for_handler",
  );
});

it("refreshes the queue every two seconds", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes = { "GET /api/claims": [queueEntry()] };
  stubApi(routes);
  render(<QueuePage />);
  const row = await screen.findByRole("row", { name: /CLM-1001/ });
  expect(within(row).getByText("Waiting")).toBeDefined();
  routes["GET /api/claims"] = [queueEntry({ status: "in_progress" })];
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(
    within(screen.getByRole("row", { name: /CLM-1001/ })).getByText(
      "In progress",
    ),
  ).toBeDefined();
});

it("says so when the claims system can't be reached", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<QueuePage />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Can't reach the claims system.",
  );
});

it("shows an error from the claims system", async () => {
  stubApi({
    "GET /api/claims": new Failure(500, "Something broke."),
  });
  render(<QueuePage />);
  expect(await screen.findByRole("alert")).toBeDefined();
});
