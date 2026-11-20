import { vi } from "vitest";
import type {
  Claim,
  Customer,
  PlanDetails,
  Policy,
  QueueEntry,
  Run,
} from "./src/types";

export function fixture() {
  const claim: Claim = {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight canceled overnight",
    story:
      "My flight was canceled because of a crew problem. I stayed at the airport hotel.",
    items: [
      { description: "Airport hotel", category: "accommodation", amount: 420 },
    ],
    amount_claimed: 420,
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "Hotel paid: $420.00.",
      },
    ],
    status: "waiting",
    decision: null,
    sign_off: null,
    payment: null,
    failures: 0,
    needs_handler: false,
    handler_reason: "",
  };
  const queue: QueueEntry[] = [
    {
      claim_id: claim.claim_id,
      customer_name: "Maya Patel",
      claim_type: claim.claim_type,
      summary: claim.summary,
      amount_claimed: claim.amount_claimed,
      status: claim.status,
      failures: 0,
      needs_handler: false,
      handler_reason: "",
    },
  ];
  const policy: Policy = {
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    plan: "premium",
    add_ons: [],
    purchased_on: "2026-04-22",
    sold_through: "Airline checkout",
    status: "active",
    trip: {
      destination: "Rome, Italy",
      departs_on: "2026-06-10",
      returns_on: "2026-06-18",
      trip_cost: 3100,
    },
    travelers: ["Maya Patel"],
  };
  const customer: Customer = {
    customer_id: "CUS-3001",
    name: "Maya Patel",
    email: "maya@example.com",
    phone: "+1 201 555 0143",
    date_of_birth: "1988-03-14",
    customer_since: "2023-04-11",
    address: { street: "48 Wayne Street", city: "Jersey City" },
    previous_claims: [
      {
        claim_id: "CLM-0412",
        filed_on: "2024-08-19",
        incident_date: "2024-08-09",
        claim_type: "baggage_delay",
        summary: "Bag arrived late",
        outcome: "approved",
        amount_paid: 140,
      },
    ],
  };
  const plan: PlanDetails = {
    plan: {
      plan: "premium",
      name: "UnderCover Premium",
      deductible: 50,
      trip_delay_waiting_hours: 6,
      trip_delay_max: 800,
    },
    add_ons: [
      {
        add_on: "electronics_plus",
        name: "Electronics Plus",
        effect: "Raises the electronics limit.",
      },
    ],
    deductible_applies_to: ["baggage", "emergency_medical"],
    electronics_per_item_limit: 1200,
  };
  const run: Run = {
    run_id: "run-1",
    thread_id: "thread-1",
    claim_id: "CLM-1001",
    status: "running",
    started_at: "2026-11-10T09:00:00Z",
    finished_at: null,
    error: null,
  };
  const handlers = [
    {
      handler_id: "HND-01",
      name: "Dana Whitfield",
      role: "Senior Claims Handler",
      can_approve_over_limit: true,
    },
  ];
  const responses = new Map<string, unknown>([
    ["/api/claims", queue],
    ["/api/claims/CLM-1001", claim],
    ["/api/policies/POL-2001", policy],
    ["/api/customers/CUS-3001", customer],
    ["/api/plans/premium", plan],
    ["/api/handlers", handlers],
    ["/api/claims/CLM-1001/runs", []],
    ["/api/claims/CLM-1001/events", []],
    ["/api/claims/CLM-1001/reads", []],
    ["/api/agent-runs", []],
    [
      "/api/documents",
      [
        {
          document_id: "manual",
          version: "2026.2",
          section: 9,
          title: "Repeat claims",
        },
      ],
    ],
    [
      "/api/documents/manual/sections/9",
      {
        document_id: "manual",
        version: "2026.2",
        section: 9,
        title: "Repeat claims",
        text: "A third claim is referred for review.",
      },
    ],
    [
      "/api/instructions/queue",
      { text: "Plan the queue and delegate fresh helpers." },
    ],
    [
      "/api/instructions/claim",
      { text: "Read the wording and manual. Record a decision." },
    ],
    [
      "/api/wording",
      { version: "2026.1", text: "## 3. Trip Delay\nReceipts are required." },
    ],
  ]);
  const fetcher = vi.fn((input: string, init?: RequestInit) => {
    if (init?.method === "POST") return Promise.resolve(Response.json({}));
    return Promise.resolve(Response.json(responses.get(input) ?? {}));
  });
  vi.stubGlobal("fetch", fetcher);
  return {
    claim,
    queue,
    policy,
    customer,
    plan,
    run,
    handlers,
    responses,
    fetcher,
  };
}

export function approve(claim: Claim, amount = 420) {
  claim.status = amount > 1000 ? "waiting_for_sign_off" : "decided";
  claim.decision = {
    run_id: "run-1",
    outcome: "approve",
    payout: amount,
    calculation: `Eligible costs: $${String(amount)}.`,
    explanation:
      "The receipts support the covered costs. The delay meets the waiting period.",
    policy_sections: [3, 10],
    manual_version: "2026.2",
    manual_sections: [4, 9],
    recorded_at: "2026-11-10T09:01:00Z",
  };
}
