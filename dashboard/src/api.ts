import type { Claim, ClaimSummary } from "./types";

export async function fetchClaims(): Promise<ClaimSummary[]> {
  const response = await fetch("/api/claims");
  return (await response.json()) as ClaimSummary[];
}

export async function fetchClaim(claimId: string): Promise<Claim> {
  const response = await fetch(`/api/claims/${claimId}`);
  return (await response.json()) as Claim;
}
