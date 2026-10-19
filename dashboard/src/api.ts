import type {
  ClaimDetail,
  ClaimSummary,
  Customer,
  Handler,
  Instructions,
  Policy,
  Run,
  Step,
} from "./types";

async function request<T>(
  method: string,
  path: string,
  body?: object,
): Promise<T> {
  const response = await fetch(
    path,
    body
      ? {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : { method },
  );
  if (!response.ok)
    throw new Error(`${method} ${path}: ${String(response.status)}`);
  const data: unknown = await response.json();
  return data as T;
}

export const health = () => request<{ status: string }>("GET", "/api/health");
export const listClaims = () => request<ClaimSummary[]>("GET", "/api/claims");
export const getClaim = (claimId: string) =>
  request<ClaimDetail>("GET", `/api/claims/${claimId}`);
export const listSteps = (claimId: string) =>
  request<Step[]>("GET", `/api/claims/${claimId}/steps`);
export const getPolicy = (policyId: string) =>
  request<Policy>("GET", `/api/policies/${policyId}`);
export const getCustomer = (customerId: string) =>
  request<Customer>("GET", `/api/customers/${customerId}`);
export const listHandlers = () => request<Handler[]>("GET", "/api/handlers");
export const getInstructions = () =>
  request<Instructions>("GET", "/api/instructions");
/** The latest run of the queue agent, or null before the first one. */
export const getLatestRun = () =>
  request<Run | null>("GET", "/api/runs/latest");
export const runClaim = (claimId: string) =>
  request<unknown>("POST", `/api/claims/${claimId}/run`);
export const runQueue = (limit: number) =>
  request<unknown>("POST", "/api/queue/run", { limit });
export const signOff = (claimId: string, handlerId: string) =>
  request<ClaimDetail>("POST", `/api/claims/${claimId}/sign-off`, {
    handler_id: handlerId,
  });
