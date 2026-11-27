import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "./api";
import { ClaimPage } from "./ClaimPage";
import { claim, handlers, mockApi, policy, steps } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const awaiting: Claim = {
  ...claim,
  status: "awaiting_signoff",
  decision: {
    decision: "approve",
    payout: 1500,
    calculation: "1500",
    reasons: "Covered.",
    policy_section: "5. Baggage",
    decided_at: "2026-11-27 14:29:06",
  },
};

const posts = (fetchMock: ReturnType<typeof mockApi>) =>
  fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");

it("starts the agent on a waiting claim", async () => {
  const fetchMock = mockApi({
    "/api/claims/CLM-1001": claim,
    "/api/claims/CLM-1001/steps": [],
    "/api/policies/POL-2001": policy,
    "POST /api/claims/CLM-1001/run": { ...claim, status: "in_progress" },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  await vi.waitFor(() => {
    expect(posts(fetchMock).map(([url]) => url)).toEqual([
      "/api/claims/CLM-1001/run",
    ]);
  });
  await vi.waitFor(() => {
    const claimReads = fetchMock.mock.calls.filter(
      ([url]) => url === "/api/claims/CLM-1001",
    );
    expect(claimReads.length).toBeGreaterThan(1);
  });
});

it("shows why the agent could not start", async () => {
  mockApi({
    "/api/claims/CLM-1001": claim,
    "/api/claims/CLM-1001/steps": [],
  });
  render(<ClaimPage claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "POST /api/claims/CLM-1001/run not found",
  );
});

it("shows the agent's steps while it works", async () => {
  mockApi({
    "/api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "/api/claims/CLM-1001/steps": [
      ...steps,
      {
        step_id: 3,
        kind: "error",
        content: "model unavailable",
        created_at: "2026-11-27 14:29:03",
      },
    ],
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect((await screen.findByRole("status")).textContent).toBe(
    "The agent is working on this claim.",
  );
  const items = within(await screen.findByRole("list")).getAllByRole(
    "listitem",
  );
  expect(items.map((item) => item.textContent)).toEqual([
    "Called14:29:01get_claim {}",
    "Result14:29:02get_claimget_claim: {...}",
    "Error14:29:03model unavailable",
  ]);
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
});

it("polls the claim and its steps", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = mockApi({
    "/api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "/api/claims/CLM-1001/steps": steps,
  });
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("status");
  const before = fetchMock.mock.calls.length;
  await act(() => vi.advanceTimersByTimeAsync(2100));
  const urls = fetchMock.mock.calls.slice(before).map(([url]) => url);
  expect(urls).toContain("/api/claims/CLM-1001");
  expect(
    urls.filter((url) => url === "/api/claims/CLM-1001/steps"),
  ).toHaveLength(2);
});

it("lets a handler sign off a payout over the limit", async () => {
  const fetchMock = mockApi({
    "/api/claims/CLM-1001": awaiting,
    "/api/claims/CLM-1001/steps": [],
    "/api/handlers": handlers,
    "POST /api/claims/CLM-1001/sign-off": { ...awaiting, status: "decided" },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText(/payment is\s+blocked/)).toBeDefined();
  const button = screen.getByRole("button", { name: "Sign off and pay" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  const select = screen.getByLabelText("Handler");
  await screen.findByRole("option", { name: /Dana Whitfield/ });
  expect(screen.queryByRole("option", { name: /Sam Trainee/ })).toBeNull();
  fireEvent.change(select, { target: { value: "HND-01" } });
  fireEvent.click(button);
  await vi.waitFor(() => {
    expect(posts(fetchMock)).toHaveLength(1);
  });
  const [url, init] = posts(fetchMock)[0];
  expect(url).toBe("/api/claims/CLM-1001/sign-off");
  expect(init?.body).toBe(JSON.stringify({ handler_id: "HND-01" }));
});
