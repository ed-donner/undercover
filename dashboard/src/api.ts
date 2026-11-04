export type Status =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
export type Decision = "approve" | "decline" | "refer";

export interface QueueEntry {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  decision: Decision | null;
  payout: number | null;
  paid_amount: number | null;
}

export interface ClaimItem {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: ClaimItem[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  decision: Decision | null;
  payout: number | null;
  reason: string | null;
  policy_section: string | null;
  decided_at: string | null;
  signed_off_by: string | null;
  signed_off_at: string | null;
  paid_amount: number | null;
  paid_at: string | null;
}

export interface AddOn {
  add_on: string;
  name: string;
  effect: string;
}

export interface Policy {
  policy_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  plan_details: { name: string; deductible: number };
  add_on_details: AddOn[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  step_id: number;
  thread_id: string;
  kind: "tool_call" | "tool_result" | "reply";
  name: string;
  content: string;
  created_at: string;
}

function errorMessage(body: unknown, status: number): string {
  if (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    typeof body.detail === "string"
  ) {
    return body.detail;
  }
  return `The claims system answered with an error (${String(status)}).`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body = (await response.json()) as unknown;
  if (!response.ok) throw new Error(errorMessage(body, response.status));
  return body as T;
}

export const listClaims = () => request<QueueEntry[]>("/api/claims");
export const getClaim = (claimId: string) =>
  request<Claim>(`/api/claims/${claimId}`);
export const listSteps = (claimId: string) =>
  request<Step[]>(`/api/claims/${claimId}/steps`);
export const getPolicy = (policyId: string) =>
  request<Policy>(`/api/policies/${policyId}`);
export const getCustomer = (customerId: string) =>
  request<Customer>(`/api/customers/${customerId}`);
export const listHandlers = () => request<Handler[]>("/api/handlers");
export const getInstructions = () =>
  request<{ text: string }>("/api/instructions");

export const signOff = (claimId: string, handlerId: string) =>
  request<Claim>(`/api/claims/${claimId}/sign-off`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handler_id: handlerId }),
  });
