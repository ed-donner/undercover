import { vi } from "vitest";
import type { ClaimDetail, ClaimSummary, Handler, Policy, Step } from "./api";

export class Failure {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {}
}

export class Replies {
  private next = 0;

  constructor(private readonly replies: unknown[]) {}

  take(): unknown {
    const reply = this.replies[Math.min(this.next, this.replies.length - 1)];
    this.next += 1;
    return reply;
  }
}

function respond(reply: unknown, key: string): Response {
  if (reply === undefined) {
    return new Response(JSON.stringify({ detail: `No mock for ${key}` }), {
      status: 404,
    });
  }
  if (reply instanceof Failure) {
    return new Response(JSON.stringify({ detail: reply.detail }), {
      status: reply.status,
    });
  }
  return new Response(JSON.stringify(reply));
}

export function mockApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${input}`;
    const route = routes[key];
    const reply = route instanceof Replies ? route.take() : route;
    return Promise.resolve(respond(reply, key));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function calls(fetchMock: ReturnType<typeof mockApi>): string[] {
  return fetchMock.mock.calls.map(
    ([input, init]) => `${init?.method ?? "GET"} ${input}`,
  );
}

export function summary(overrides: Partial<ClaimSummary> = {}): ClaimSummary {
  return {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled by the airline",
    amount_claimed: 420,
    submitted_on: "2026-06-24",
    status: "waiting",
    decision: null,
    payout: null,
    ...overrides,
  };
}

export function claim(overrides: Partial<ClaimDetail> = {}): ClaimDetail {
  return {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled by the airline",
    amount_claimed: 420,
    submitted_on: "2026-06-24",
    status: "waiting",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    story: "My flight home from Rome was canceled.",
    items: [
      {
        description: "Airport hotel, one night",
        category: "hotel",
        amount: 245,
      },
    ],
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "Hotel Aurelia. Total paid: $245.00.",
      },
    ],
    decision: null,
    sign_off: null,
    payment: null,
    ...overrides,
  };
}

export const policy: Policy = {
  policy_id: "POL-2001",
  plan: "premium",
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  plan_details: { name: "UnderCover Premium" },
  add_on_details: [{ add_on: "electronics_plus", name: "Electronics Plus" }],
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
];

export function step(id: number, overrides: Partial<Step> = {}): Step {
  return {
    id,
    kind: "tool_call",
    text: `get_claim({"claim_id": "CLM-1001"}) ${String(id)}`,
    created_at: "2026-10-28T10:00:00+00:00",
    ...overrides,
  };
}
