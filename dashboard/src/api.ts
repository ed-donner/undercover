import type { Claim, ClaimSummary, Handler, Run, Step } from "./types";

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

export const fetchClaims = () => getJson<ClaimSummary[]>("/api/claims");

export const fetchClaim = (claimId: string) =>
  getJson<Claim>(`/api/claims/${claimId}`);

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

export const payClaim = (claimId: string, amount: number) =>
  post(`/api/claims/${claimId}/payment`, { amount });
