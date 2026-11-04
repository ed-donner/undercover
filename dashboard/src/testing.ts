import { vi } from "vitest";
import type { QueueEntry } from "./api";

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
