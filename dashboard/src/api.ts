import type { Claim, ClaimSummary, Handler, Run, Step } from "./types";

export async function fetchClaims(): Promise<ClaimSummary[]> {
  const response = await fetch("/api/claims");
  return (await response.json()) as ClaimSummary[];
}

export async function fetchClaim(claimId: string): Promise<Claim> {
  const response = await fetch(`/api/claims/${claimId}`);
  return (await response.json()) as Claim;
}

export async function fetchSteps(claimId: string): Promise<Step[]> {
  const response = await fetch(`/api/claims/${claimId}/steps`);
  return (await response.json()) as Step[];
}

export async function fetchClaimInstructions(): Promise<string> {
  const response = await fetch("/api/claim-instructions");
  const body = (await response.json()) as { instructions: string };
  return body.instructions;
}

export async function fetchQueueInstructions(): Promise<string> {
  const response = await fetch("/api/queue-instructions");
  const body = (await response.json()) as { instructions: string };
  return body.instructions;
}

export async function fetchCurrentRun(): Promise<Run | null> {
  const response = await fetch("/api/runs/current");
  if (!response.ok) return null;
  return (await response.json()) as Run;
}

export async function runAgent(claimId: string): Promise<void> {
  await fetch(`/api/claims/${claimId}/run`, { method: "POST" });
}

export async function fetchHandlers(): Promise<Handler[]> {
  const response = await fetch("/api/handlers");
  return (await response.json()) as Handler[];
}

export async function signOffClaim(
  claimId: string,
  handlerId: string,
): Promise<void> {
  await fetch(`/api/claims/${claimId}/sign-off`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handler_id: handlerId }),
  });
}

export async function payClaim(claimId: string, amount: number): Promise<void> {
  await fetch(`/api/claims/${claimId}/payment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
}
