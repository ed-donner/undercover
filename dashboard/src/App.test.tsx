import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { requestUrl } from "./testHelpers";
import type { FetchInput } from "./testHelpers";
import type { Claim, ClaimSummary, Step } from "./types";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const claims: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    amount_claimed: 420,
    status: "waiting",
  },
];

const claim: Claim = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight home canceled",
  story: "My flight home was canceled.",
  items: [],
  amount_claimed: 420,
  documents: [],
  status: "waiting",
  decision: null,
  payout: null,
  reason: null,
  policy_reference: null,
  decided_on: null,
  over_approval_limit: null,
  signed_off_by: null,
  signed_off_on: null,
  paid_amount: null,
  paid_on: null,
  policy: {
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    plan: "premium",
    add_ons: [],
    purchased_on: "2026-04-22",
    sold_through: "Meridian Air checkout",
    trip: {
      destination: "Rome, Italy",
      departs_on: "2026-06-10",
      returns_on: "2026-06-18",
      trip_cost: 3100,
    },
    travelers: ["Maya Patel"],
    status: "active",
  },
  customer_previous_claims: [],
};

function bodyFor(url: string): unknown {
  if (url === "/api/claims") return claims;
  if (url.endsWith("/steps")) return [] as Step[];
  return claim;
}

function mockFetch() {
  const impl = (input: FetchInput): Promise<Response> => {
    const url = requestUrl(input);
    if (url.endsWith("/runs/current")) {
      return Promise.resolve(new Response(null, { status: 404 }));
    }
    return Promise.resolve(new Response(JSON.stringify(bodyFor(url))));
  };
  vi.stubGlobal("fetch", vi.fn(impl));
}

it("shows the queue and navigates to a claim", async () => {
  mockFetch();
  render(<App />);

  expect(await screen.findByText("CLM-1001")).toBeDefined();

  fireEvent.click(screen.getByRole("link", { name: "CLM-1001" }));

  expect(await screen.findByText("The story")).toBeDefined();
});
