export type ClaimStatus =
  "waiting" | "in_progress" | "awaiting_sign_off" | "decided";

export type DecisionKind = "approve" | "decline" | "refer";

interface ClaimBase {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: ClaimStatus;
}

export interface ClaimSummary extends ClaimBase {
  decision: DecisionKind | null;
  payout: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: DecisionKind;
  payout: number;
  reason: string;
  policy_section: string;
  decided_at: string;
}

export interface ClaimDetail extends ClaimBase {
  policy_id: string;
  customer_id: string;
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: ClaimDocument[];
  decision: Decision | null;
  sign_off: { handler_id: string; signed_off_at: string } | null;
  payment: { amount: number; paid_at: string } | null;
}

export interface Policy {
  policy_id: string;
  plan: string;
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  plan_details: { name: string };
  add_on_details: { add_on: string; name: string }[];
}

export interface Step {
  id: number;
  kind: "tool_call" | "tool_result" | "reply" | "error";
  text: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

function detail(body: unknown): string {
  if (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    typeof body.detail === "string"
  ) {
    return body.detail;
  }
  return "Something went wrong. Please try again.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body: unknown = await response.json();
  if (!response.ok) throw new Error(detail(body));
  return body as T;
}

function post<T>(path: string, data?: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
}

export const api = {
  claims: () => request<ClaimSummary[]>("/api/claims"),
  claim: (claimId: string) => request<ClaimDetail>(`/api/claims/${claimId}`),
  policy: (policyId: string) => request<Policy>(`/api/policies/${policyId}`),
  steps: (claimId: string) => request<Step[]>(`/api/claims/${claimId}/steps`),
  instructions: () => request<{ text: string }>("/api/instructions"),
  handlers: () => request<Handler[]>("/api/handlers"),
  runAgent: (claimId: string) =>
    post<{ status: string }>(`/api/claims/${claimId}/run`),
  runQueue: () => post<{ waiting: number }>("/api/queue/run"),
  signOff: (claimId: string, handlerId: string) =>
    post<ClaimDetail>(`/api/claims/${claimId}/sign-off`, {
      handler_id: handlerId,
    }),
};
