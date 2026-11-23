export type ClaimState =
  "waiting" | "in progress" | "waiting for sign-off" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";
export type StepKind = "tool_call" | "tool_result" | "message" | "error";

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface Document {
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
  items: Item[];
  amount_claimed: number;
  documents: Document[];
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
}

export interface PlanLimits {
  plan: string;
  name: string;
  deductible: number;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface DecisionRecord {
  decision: DecisionKind;
  payout: number;
  explanation: string;
  policy_section: string;
  decided_at: string;
}

export interface Payment {
  amount: number;
  signed_off_by: string | null;
  paid_at: string;
}

export interface ClaimDetail {
  claim: Claim;
  policy: Policy;
  plan: PlanLimits;
  customer: Customer;
  state: ClaimState;
  decision: DecisionRecord | null;
  payment: Payment | null;
}

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  state: ClaimState;
  decision: DecisionKind | null;
  payout: number | null;
}

export interface Step {
  id: number;
  kind: StepKind;
  text: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface RunStatus {
  active: boolean;
  claim_id: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = (await response.json()) as { detail: string };
    throw new Error(body.detail);
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body?: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const listClaims = () => request<ClaimSummary[]>("/api/claims");
export const getClaim = (id: string) =>
  request<ClaimDetail>(`/api/claims/${id}`);
export const listSteps = (id: string) =>
  request<Step[]>(`/api/claims/${id}/steps`);
export const listHandlers = () => request<Handler[]>("/api/handlers");
export const getRunStatus = () => request<RunStatus>("/api/runs/current");
export const getInstructions = () =>
  request<{ text: string }>("/api/instructions").then((body) => body.text);
export const startClaimRun = (id: string) =>
  post<RunStatus>(`/api/claims/${id}/run`);
export const startQueueRun = () => post<RunStatus>("/api/runs");
export const signOffClaim = (id: string, handlerId: string) =>
  post<Payment>(`/api/claims/${id}/sign-off`, { handler_id: handlerId });
