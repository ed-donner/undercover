import type {
  ClaimDetail,
  ClaimSummary,
  Customer,
  Handler,
  Policy,
  QueueRun,
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
  request<{ queue: string; claim: string }>("GET", "/api/instructions");
export const runClaim = (claimId: string) =>
  request<unknown>("POST", `/api/claims/${claimId}/run`);
export const runQueue = () => request<QueueRun>("POST", "/api/queue/run");
export const signOff = (claimId: string, handlerId: string) =>
  request<ClaimDetail>("POST", `/api/claims/${claimId}/sign-off`, {
    handler_id: handlerId,
  });
