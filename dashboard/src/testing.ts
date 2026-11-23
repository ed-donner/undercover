import { vi } from "vitest";
import type {
  ClaimDetail,
  ClaimState,
  ClaimSummary,
  Handler,
  RunStatus,
  Step,
} from "./api";

/** A stubbed answer that the backend refuses, with its reason. */
export class Refusal {
  constructor(readonly detail: string) {}
}

export interface Call {
  key: string;
  body: unknown;
}

/** Stub fetch with answers by "METHOD /path". Returns the calls made. */
export function stubApi(routes: Record<string, unknown>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${url}`;
      calls.push({
        key,
        body:
          typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      if (!(key in routes)) {
        return Promise.resolve(
          Response.json({ detail: `No stub for ${key}` }, { status: 404 }),
        );
      }
      const answer = routes[key];
      if (answer instanceof Refusal) {
        return Promise.resolve(
          Response.json({ detail: answer.detail }, { status: 409 }),
        );
      }
      return Promise.resolve(Response.json(answer));
    }),
  );
  return calls;
}

export const idle: RunStatus = { active: false, claim_id: null };

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-02",
    name: "Marcus Oyelaran",
    role: "Claims Handler",
    can_approve_over_limit: true,
  },
];

export function summary(
  number: number,
  state: ClaimState = "waiting",
): ClaimSummary {
  return {
    claim_id: `CLM-${String(1000 + number)}`,
    customer_name: `Customer ${String(number)}`,
    claim_type: "trip_delay",
    summary: "A delayed flight",
    submitted_on: "2026-06-24",
    amount_claimed: 1250 + number,
    state,
    decision: null,
    payout: null,
  };
}

export function detail(overrides: Partial<ClaimDetail> = {}): ClaimDetail {
  return {
    claim: {
      claim_id: "CLM-1001",
      policy_id: "POL-2001",
      customer_id: "CUS-3001",
      claim_type: "trip_delay",
      submitted_on: "2026-06-24",
      incident_date: "2026-06-18",
      incident_location: "Rome, Italy",
      summary: "Flight home canceled by the airline",
      story: "My flight was canceled and I stayed a night.",
      items: [
        {
          description: "Airport hotel",
          category: "accommodation",
          amount: 245,
        },
        { description: "Taxis", category: "transport", amount: 80 },
      ],
      amount_claimed: 325,
      documents: [
        {
          name: "Hotel receipt",
          type: "receipt",
          content: "Hotel Aurelia, $245.00",
        },
      ],
    },
    policy: {
      policy_id: "POL-2001",
      plan: "premium",
      add_ons: ["electronics_plus"],
      purchased_on: "2026-04-22",
      sold_through: "Meridian Air checkout",
      trip: {
        destination: "Rome, Italy",
        departs_on: "2026-06-10",
        returns_on: "2026-06-18",
        trip_cost: 3100,
      },
      travelers: ["Maya Patel"],
    },
    plan: { plan: "premium", name: "UnderCover Premium", deductible: 50 },
    customer: {
      customer_id: "CUS-3001",
      name: "Maya Patel",
      customer_since: "2023-04-11",
      previous_claims: [
        {
          claim_id: "CLM-0412",
          filed_on: "2024-08-19",
          incident_date: "2024-08-09",
          claim_type: "baggage_delay",
          summary: "Checked bag arrived 30 hours late",
          outcome: "approved",
          amount_paid: 140,
        },
      ],
    },
    state: "waiting",
    decision: null,
    payment: null,
    ...overrides,
  };
}

export const steps: Step[] = [
  {
    id: 1,
    kind: "tool_call",
    text: 'get_claim_context({"claim_id": "CLM-1001"})',
    created_at: "2026-11-23T10:00:00+00:00",
  },
  {
    id: 2,
    kind: "message",
    text: "Approved, $325.00.",
    created_at: "2026-11-23T10:00:05+00:00",
  },
];
