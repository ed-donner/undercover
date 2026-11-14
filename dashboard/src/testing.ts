import { vi } from "vitest";
import type { Claim, ClaimSummary } from "./api";

export type Routes = Record<string, unknown>;

export function fakeFetch(routes: Routes) {
  const fetch = vi.fn((path: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${path}`;
    const found = routes[key];
    if (found === undefined)
      return Promise.resolve(Response.json({}, { status: 404 }));
    const value: unknown =
      typeof found === "function" ? (found as () => unknown)() : found;
    if (value instanceof Response) return Promise.resolve(value);
    return Promise.resolve(Response.json(value));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

export const summary = (
  overrides: Partial<ClaimSummary> = {},
): ClaimSummary => ({
  claim_id: "CLM-1001",
  claim_type: "trip_delay",
  summary: "Flight home canceled",
  amount_claimed: 1250,
  submitted_on: "2026-06-24",
  status: "waiting",
  decision: null,
  ...overrides,
});

export const claim = (overrides: Partial<Claim> = {}): Claim => ({
  ...summary(),
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  story: "My flight home from Rome was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
  ],
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "One night: $245.00." },
  ],
  payout: null,
  reason: null,
  policy_section: null,
  decided_at: null,
  signed_off_by: null,
  signed_off_at: null,
  paid_amount: null,
  paid_at: null,
  ...overrides,
});
