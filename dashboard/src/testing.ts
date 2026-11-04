import { vi } from "vitest";
import type { Claim, Customer, Handler, Policy, QueueEntry } from "./api";

/** A reply from the API with an error status. */
export class Failure {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {}
}

/** Stub fetch so each "METHOD /path" in routes answers with its JSON reply. */
export function stubApi(routes: Record<string, unknown>) {
  const fetchStub = vi.fn((url: string, init?: RequestInit) => {
    const reply =
      routes[`${init?.method ?? "GET"} ${url}`] ?? new Failure(404, "None");
    if (reply instanceof Failure) {
      return Promise.resolve(
        Response.json({ detail: reply.detail }, { status: reply.status }),
      );
    }
    return Promise.resolve(Response.json(reply));
  });
  vi.stubGlobal("fetch", fetchStub);
  return fetchStub;
}

export function queueEntry(overrides: Partial<QueueEntry> = {}): QueueEntry {
  return {
    claim_id: "CLM-1001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    summary: "Flight home canceled by the airline",
    submitted_on: "2026-06-24",
    amount_claimed: 1250,
    status: "waiting",
    decision: null,
    payout: null,
    paid_amount: null,
    ...overrides,
  };
}

export function claim(overrides: Partial<Claim> = {}): Claim {
  return {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled by the airline",
    story: "My flight home from Rome was canceled.",
    items: [
      { description: "Airport hotel", category: "accommodation", amount: 245 },
      { description: "Taxis", category: "transport", amount: 175 },
    ],
    amount_claimed: 420,
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "One night. Total paid: $245.00.",
      },
    ],
    status: "waiting",
    decision: null,
    payout: null,
    reason: null,
    policy_section: null,
    decided_at: null,
    signed_off_by: null,
    signed_off_at: null,
    paid_amount: null,
    paid_at: null,
    ...overrides,
  };
}

export const policy: Policy = {
  policy_id: "POL-2001",
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
  plan_details: { name: "UnderCover Premium", deductible: 50 },
  add_on_details: [],
};

export const customer: Customer = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  email: "maya.patel@example.com",
  phone: "+1 201 555 0143",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-02",
    name: "Marcus Oyelaran",
    can_approve_over_limit: true,
  },
  { handler_id: "HND-03", name: "Priya Raman", can_approve_over_limit: false },
];

/** The API routes a claim page loads, for the claim given. */
export function claimRoutes(shown: Claim): Record<string, unknown> {
  return {
    [`GET /api/claims/${shown.claim_id}`]: shown,
    [`GET /api/claims/${shown.claim_id}/steps`]: [],
    "GET /api/policies/POL-2001": policy,
    "GET /api/customers/CUS-3001": customer,
    "GET /api/handlers": handlers,
  };
}
