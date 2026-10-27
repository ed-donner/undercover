import type { Claim, ClaimSummary, Step } from "./types";

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

export async function fetchInstructions(): Promise<string> {
  const response = await fetch("/api/agent-instructions");
  const body = (await response.json()) as { instructions: string };
  return body.instructions;
}

export async function runAgent(claimId: string): Promise<void> {
  await fetch(`/api/claims/${claimId}/run`, { method: "POST" });
}
