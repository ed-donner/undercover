import type { ClaimSummary, QueueRun } from "./types";

async function request<T>(method: string, path: string): Promise<T> {
  const response = await fetch(path, { method });
  if (!response.ok)
    throw new Error(`${method} ${path}: ${String(response.status)}`);
  const data: unknown = await response.json();
  return data as T;
}

export const health = () => request<{ status: string }>("GET", "/api/health");
export const listClaims = () => request<ClaimSummary[]>("GET", "/api/claims");
export const runClaim = (claimId: string) =>
  request<unknown>("POST", `/api/claims/${claimId}/run`);
export const runQueue = () => request<QueueRun>("POST", "/api/queue/run");
