import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Claim } from "../api";
import { claim, mockApi, policy } from "../testing";
import { REFRESH_MS } from "../useData";
import { ClaimPage } from "./ClaimPage";

const approved: Claim = {
  ...claim,
  status: "awaiting_signoff",
  decision: {
    decision: "approve",
    payout: 1500,
    reason: "Covered.",
    policy_section: "Section 7",
  },
};
const handlers = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
];
const step = (id: number, text: string) => ({
  id,
  text,
  created_at: "2026-11-26 13:00:0" + String(id),
});

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function tick() {
  await act(() => vi.advanceTimersByTimeAsync(REFRESH_MS));
}

function claimCalls(fetch: ReturnType<typeof mockApi>) {
  return fetch.mock.calls.filter(([path]) => path === "/api/claims/CLM-1001")
    .length;
}

it("shows steps as they arrive", async () => {
  const routes: Record<string, unknown> = {
    "/api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "/api/claims/CLM-1001/policy": policy,
    "/api/claims/CLM-1001/steps": [],
  };
  mockApi(routes);
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent has not started on this claim."),
  ).toBeDefined();

  routes["/api/claims/CLM-1001/steps"] = [
    step(1, "Calling start_claim"),
    step(2, "Calling get_policy"),
  ];
  await tick();
  expect(screen.getByText("Calling get_policy")).toBeDefined();
  expect(screen.getByText("13:00:02")).toBeDefined();
});

it("stops polling the claim once it is decided", async () => {
  const routes: Record<string, unknown> = {
    "/api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "/api/claims/CLM-1001/policy": policy,
    "/api/claims/CLM-1001/steps": [],
  };
  const fetch = mockApi(routes);
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByText("In progress");

  routes["/api/claims/CLM-1001"] = {
    ...approved,
    status: "decided",
    payment: { amount: 1500, signed_off_by: null },
  };
  await tick();
  expect(screen.getByText("Decided")).toBeDefined();
  const calls = claimCalls(fetch);
  await tick();
  await tick();
  expect(claimCalls(fetch)).toBe(calls);
});

it("signs off a payout and shows it paid", async () => {
  const routes: Record<string, unknown> = {
    "/api/claims/CLM-1001": approved,
    "/api/claims/CLM-1001/policy": policy,
    "/api/claims/CLM-1001/steps": [],
    "/api/handlers": handlers,
    "POST /api/claims/CLM-1001/signoff": {},
  };
  const fetch = mockApi(routes);
  render(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off and pay $1,500.00",
  });
  expect(button).toHaveProperty("disabled", true);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });

  routes["/api/claims/CLM-1001"] = {
    ...approved,
    status: "decided",
    payment: { amount: 1500, signed_off_by: "Dana Whitfield" },
  };
  fireEvent.click(button);
  expect(await screen.findByText(/signed off by Dana Whitfield/)).toBeDefined();
  expect(screen.queryByRole("button")).toBeNull();
  const [, init] = fetch.mock.calls.find(([, i]) => i?.method === "POST") ?? [];
  expect(init?.body).toBe(JSON.stringify({ handler_id: "HND-01" }));
});

it("shows a failed sign-off", async () => {
  mockApi({
    "/api/claims/CLM-1001": approved,
    "/api/claims/CLM-1001/policy": policy,
    "/api/claims/CLM-1001/steps": [],
    "/api/handlers": handlers,
  });
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button"));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Could not sign off",
  );
});

it("has no sign-off for a declined claim", async () => {
  mockApi({
    "/api/claims/CLM-1001": {
      ...claim,
      status: "decided",
      decision: {
        decision: "decline",
        payout: 0,
        reason: "Not covered.",
        policy_section: "Section 9",
      },
    },
    "/api/claims/CLM-1001/policy": policy,
    "/api/claims/CLM-1001/steps": [],
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Not covered.")).toBeDefined();
  expect(screen.queryByRole("region", { name: "Sign-off" })).toBeNull();
});
