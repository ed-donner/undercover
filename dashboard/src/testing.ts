import { vi } from "vitest";
import type { Claim, ClaimSummary, Run } from "./api";

export function stubApi(
  routes: Record<string, unknown>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const path = typeof input === "string" ? input : "";
    if (path in routes) return Promise.resolve(Response.json(routes[path]));
    return Promise.resolve(new Response("{}", { status: 404 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const summary: ClaimSummary = {
  claim_id: "CLM-1001",
  claim_type: "trip_delay",
  summary: "Flight canceled",
  amount_claimed: 420,
  status: "decided",
  decision: "approve",
  payout: 420,
  paid: 420,
};

export const run: Run = {
  id: 1,
  limit: 5,
  summary: "Approved one claim.",
  finished: false,
  claims: ["CLM-1001"],
  todos: [
    { text: "CLM-1001", status: "done" },
    { text: "CLM-1002", status: "in_progress" },
  ],
};

export const claim: Claim = {
  ...summary,
  story: "My flight was canceled.",
  incident_location: "Rome, Italy",
  incident_date: "2026-06-18",
  items: [{ description: "Hotel", category: "accommodation", amount: 420 }],
  documents: [],
  reason: "Covered delay.",
  policy_section: "Wording section 3",
  attempts: 0,
  signed_off_by: null,
  steps: [
    { kind: "started", text: "Started in run 1", created_at: "1" },
    {
      kind: "read",
      text: "Read claims_manual section 9: Repeat claims",
      created_at: "2",
    },
  ],
};
