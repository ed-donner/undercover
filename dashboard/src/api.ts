import { parseCents } from "./money";
import type { Claim, ClaimSummary, Handler, Item, Run, Step } from "./types";

type WireSummary = Omit<ClaimSummary, "amount_claimed"> & {
  amount_claimed: string;
};

type WireClaim = Omit<
  Claim,
  "amount_claimed" | "items" | "payout" | "paid_amount"
> & {
  amount_claimed: string;
  items: (Omit<Item, "amount"> & { amount: string })[];
  payout: string | null;
  paid_amount: string | null;
};

const optionalCents = (amount: string | null) =>
  amount === null ? null : parseCents(amount);

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${String(response.status)}`);
  return (await response.json()) as T;
}

async function post(path: string, body?: object): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body && JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path}: ${String(response.status)}`);
}

async function getInstructions(path: string): Promise<string> {
  return (await getJson<{ instructions: string }>(path)).instructions;
}

export async function fetchClaims(): Promise<ClaimSummary[]> {
  const claims = await getJson<WireSummary[]>("/api/claims");
  return claims.map((claim) => ({
    ...claim,
    amount_claimed: parseCents(claim.amount_claimed),
  }));
}

export async function fetchClaim(claimId: string): Promise<Claim> {
  const claim = await getJson<WireClaim>(`/api/claims/${claimId}`);
  return {
    ...claim,
    amount_claimed: parseCents(claim.amount_claimed),
    items: claim.items.map((item) => ({
      ...item,
      amount: parseCents(item.amount),
    })),
    payout: optionalCents(claim.payout),
    paid_amount: optionalCents(claim.paid_amount),
  };
}

export const fetchSteps = (claimId: string) =>
  getJson<Step[]>(`/api/claims/${claimId}/steps`);

export const fetchHandlers = () => getJson<Handler[]>("/api/handlers");

export const fetchClaimInstructions = () =>
  getInstructions("/api/claim-instructions");

export const fetchQueueInstructions = () =>
  getInstructions("/api/queue-instructions");

/** The most recent run, or null before the first one. */
export async function fetchCurrentRun(): Promise<Run | null> {
  const response = await fetch("/api/runs/current");
  if (response.status === 404) return null;
  if (!response.ok)
    throw new Error(`/api/runs/current: ${String(response.status)}`);
  return (await response.json()) as Run;
}

export const runAgent = (claimId: string) => post(`/api/claims/${claimId}/run`);

export const signOffClaim = (claimId: string, handlerId: string) =>
  post(`/api/claims/${claimId}/sign-off`, { handler_id: handlerId });
