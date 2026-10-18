import type { ClaimDetail, Customer, Handler, Policy, Step } from "./types";

export function detail(overrides: Partial<ClaimDetail> = {}): ClaimDetail {
  return {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled",
    story: "My flight home was canceled by the airline.",
    items: [
      { description: "Airport hotel", category: "accommodation", amount: 245 },
    ],
    amount_claimed: 245,
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "Hotel Aurelia, $245.00.",
      },
    ],
    status: "waiting",
    decision: null,
    payment: null,
    sign_off: null,
    ...overrides,
  };
}

export const POLICY: Policy = {
  policy_id: "POL-2001",
  plan: "premium",
  add_ons: ["electronics_plus"],
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
};

export const CUSTOMER: Customer = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const HANDLERS: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];

export function step(id: number, kind: Step["kind"], text: string): Step {
  return { id, kind, text, created_at: "2026-10-18T09:00:00+00:00" };
}

export function claimRoutes(claim: ClaimDetail, steps: Step[] = []) {
  return {
    [`GET /api/claims/${claim.claim_id}`]: claim,
    [`GET /api/claims/${claim.claim_id}/steps`]: steps,
    "GET /api/policies/POL-2001": POLICY,
    "GET /api/customers/CUS-3001": CUSTOMER,
    "GET /api/handlers": HANDLERS,
  };
}
