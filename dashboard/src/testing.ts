import { vi } from "vitest";
import type { Claim, ClaimSummary, Handler, Policy, Step } from "./api";

export const summary: ClaimSummary = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  summary: "Flight home canceled by the airline",
  amount_claimed: 420,
  status: "waiting",
};

export const claim: Claim = {
  ...summary,
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  story: "My flight home from Rome was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
    { description: "Dinner and breakfast", category: "meals", amount: 95 },
    { description: "Taxis", category: "transport", amount: 80 },
  ],
  documents: [
    {
      name: "Hotel receipt",
      type: "receipt",
      content: "One night: $245.00.",
    },
  ],
  decision: null,
  payment: null,
  sign_off: null,
};

export const policy: Policy = {
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
  plan_details: { name: "UnderCover Premium", deductible: 50 },
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-09",
    name: "Sam Trainee",
    role: "Trainee",
    can_approve_over_limit: false,
  },
];

export const steps: Step[] = [
  {
    step_id: 1,
    kind: "tool_call",
    content: "get_claim {}",
    created_at: "2026-11-27 14:29:01",
  },
  {
    step_id: 2,
    kind: "tool_result",
    content: "get_claim: {...}",
    created_at: "2026-11-27 14:29:02",
  },
];

export type Routes = Record<string, unknown>;

/** Stub fetch: GET replies come from routes[url], POSTs from routes["POST url"]. */
export function mockApi(routes: Routes) {
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const key = init?.method === "POST" ? `POST ${input}` : input;
    const body = routes[key];
    if (body instanceof Error) return Promise.reject(body);
    return Promise.resolve(
      body === undefined
        ? new Response(JSON.stringify({ detail: `${key} not found` }), {
            status: 404,
          })
        : new Response(JSON.stringify(body)),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
