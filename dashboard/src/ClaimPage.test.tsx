import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "./api";
import { ClaimPage } from "./ClaimPage";
import { claim, mockApi, policy } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const decided: Claim = {
  ...claim,
  status: "decided",
  decision: {
    decision: "approve",
    payout: 1500,
    calculation: "245 + 95 + 80 = 420",
    reasons: "The airline canceled the flight.",
    policy_section: "3. Trip Delay",
    decided_at: "2026-11-27 14:29:06",
  },
  payment: { amount: 1500, paid_at: "2026-11-27 14:30:00" },
  sign_off: {
    handler_id: "HND-01",
    handler_name: "Dana Whitfield",
    signed_at: "2026-11-27 14:30:00",
  },
};

it("shows a claim the agent has not decided", async () => {
  mockApi({ "/api/claims/CLM-1001": claim, "/api/policies/POL-2001": policy });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText(claim.story)).toBeDefined();
  expect(
    screen.getByText("The agent has not decided this claim yet."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("Electronics plus")).toBeDefined();
  expect(
    screen.getByText("Rome, Italy, Jun 10, 2026 to Jun 18, 2026"),
  ).toBeDefined();
});

it("shows the decision, the payment and the sign-off", async () => {
  mockApi({
    "/api/claims/CLM-1001": decided,
    "/api/policies/POL-2001": { ...policy, add_ons: [] },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Approved")).toBeDefined();
  expect(screen.getByText("The airline canceled the flight.")).toBeDefined();
  expect(screen.getByText("3. Trip Delay")).toBeDefined();
  expect(screen.getByText("Paid $1,500.00 on Nov 27, 2026")).toBeDefined();
  expect(screen.getByText("Dana Whitfield")).toBeDefined();
  expect(await screen.findByText("None")).toBeDefined();
});

it("says when a decision is not paid", async () => {
  mockApi({
    "/api/claims/CLM-1001": { ...decided, payment: null, sign_off: null },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Not paid")).toBeDefined();
});

it("shows an error for an unknown claim", async () => {
  mockApi({});
  render(<ClaimPage claimId="CLM-9999" />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "/api/claims/CLM-9999 not found",
  );
});
