import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import type { Claim, Handler } from "../types";
import { PaymentPanel } from "./PaymentPanel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function makeClaim(overrides: Partial<Claim>): Claim {
  return {
    claim_id: "CLM-1003",
    policy_id: "POL-2003",
    customer_id: "CUS-3003",
    claim_type: "emergency_medical",
    submitted_on: "2026-06-01",
    incident_date: "2026-05-30",
    incident_location: "Lisbon, Portugal",
    summary: "Hospital visit abroad",
    story: "Fractured my wrist.",
    items: [],
    amount_claimed: 120000,
    documents: [],
    status: "waiting for sign-off",
    decision: "approve",
    payout: 120000,
    reason: "A covered emergency medical claim.",
    policy_reference: "Section 7",
    decided_on: "2026-06-02T00:00:00+00:00",
    over_approval_limit: 1,
    signed_off_by: null,
    signed_off_on: null,
    paid_amount: null,
    paid_on: null,
    policy: {
      policy_id: "POL-2003",
      customer_id: "CUS-3003",
      plan: "first",
      add_ons: [],
      purchased_on: "2026-01-01",
      sold_through: "Direct",
      trip: {
        destination: "Lisbon, Portugal",
        departs_on: "2026-05-28",
        returns_on: "2026-06-05",
      },
      travelers: ["Alex Rivera"],
      status: "active",
    },
    customer_previous_claims: [],
    ...overrides,
  };
}

const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    email: "dana.whitfield@undercover.example",
    can_approve_over_limit: true,
  },
];

it("lets a handler sign off an over-limit claim", async () => {
  const calls: string[] = [];
  const impl = (input: FetchInput): Promise<Response> => {
    const url = requestUrl(input);
    calls.push(url);
    if (url === "/api/handlers") {
      return Promise.resolve(new Response(JSON.stringify(handlers)));
    }
    return Promise.resolve(new Response(JSON.stringify({})));
  };
  vi.stubGlobal("fetch", vi.fn(impl));

  const claim = makeClaim({ status: "waiting for sign-off" });
  render(<PaymentPanel claim={claim} onUpdated={() => undefined} />);

  const button = await screen.findByRole("button", {
    name: "Sign off as Dana Whitfield",
  });
  fireEvent.click(button);

  expect(calls).toContain("/api/claims/CLM-1003/sign-off");
});

it("shows a signed-off claim as awaiting payment", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(handlers))),
  );

  const claim = makeClaim({
    status: "in progress",
    signed_off_by: "HND-01",
    signed_off_on: "2026-06-03T14:30:00+00:00",
  });
  render(<PaymentPanel claim={claim} onUpdated={() => undefined} />);

  expect(
    await screen.findByText(/Signed off by Dana Whitfield on/),
  ).toBeDefined();
  expect(screen.getByText("Payment in progress.")).toBeDefined();
  expect(screen.queryByRole("button")).toBeNull();
});

it("shows the paid amount once a claim has been paid", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(handlers))),
  );
  const claim = makeClaim({
    status: "decided",
    paid_amount: 120000,
    paid_on: "2026-06-03T00:00:00+00:00",
    signed_off_by: "HND-01",
    signed_off_on: "2026-06-02T09:00:00+00:00",
  });

  render(<PaymentPanel claim={claim} onUpdated={() => undefined} />);

  expect(screen.getByText("Paid $1,200.00.")).toBeDefined();
  expect(
    await screen.findByText(/Signed off by Dana Whitfield on/),
  ).toBeDefined();
});
