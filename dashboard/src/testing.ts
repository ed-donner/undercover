import { vi } from "vitest";
import type { Claim, ClaimSummary, Policy } from "./api";

export function mockApi(routes: Record<string, unknown>) {
  const fetch = vi.fn((path: string, init?: RequestInit) => {
    const key = init?.method ? `${init.method} ${path}` : path;
    if (!(key in routes)) {
      return Promise.resolve(new Response("{}", { status: 404 }));
    }
    return Promise.resolve(new Response(JSON.stringify(routes[key])));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

export const summary: ClaimSummary = {
  claim_id: "CLM-1001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  summary: "Flight home canceled",
  submitted_on: "2026-06-24",
  amount_claimed: 420,
  status: "waiting",
  decision: null,
  payout: null,
};

export const claim: Claim = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight home canceled",
  story: "My flight home from Rome was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
    { description: "Meals", category: "meals", amount: 175 },
  ],
  amount_claimed: 420,
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Total paid: $245.00." },
  ],
  status: "waiting",
  decision: null,
  payment: null,
};

export const policy: Policy = {
  policy_id: "POL-2001",
  plan: { name: "UnderCover Premium", deductible: 50 },
  add_ons: [],
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  status: "active",
};
