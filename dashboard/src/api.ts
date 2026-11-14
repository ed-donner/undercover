export type Status = "waiting" | "in_progress" | "awaiting_signoff" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
  decision: DecisionKind | null;
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

export interface Claim extends ClaimSummary {
  policy_id: string;
  customer_id: string;
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: ClaimDocument[];
  payout: number | null;
  reason: string | null;
  policy_section: string | null;
  decided_at: string | null;
  signed_off_by: string | null;
  signed_off_at: string | null;
  paid_amount: number | null;
  paid_at: string | null;
}

export interface Policy {
  policy_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  plan_details: { name: string; deductible: number };
  add_on_details: { add_on: string; name: string; effect: string }[];
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface History {
  customer_id: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  kind: "tool_call" | "tool_result" | "message" | "error";
  content: string;
  created_at: string;
}

async function request<T>(method: string, path: string, body?: unknown) {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const { detail } = (await response.json()) as { detail?: unknown };
    throw new Error(
      typeof detail === "string" ? detail : "The request was not accepted",
    );
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  listClaims: () => request<ClaimSummary[]>("GET", "/api/claims"),
  getClaim: (id: string) => request<Claim>("GET", `/api/claims/${id}`),
  listSteps: (id: string) => request<Step[]>("GET", `/api/claims/${id}/steps`),
  runAgent: (id: string) => request<unknown>("POST", `/api/claims/${id}/run`),
  signOff: (id: string, handlerId: string) =>
    request<Claim>("POST", `/api/claims/${id}/signoff`, {
      handler_id: handlerId,
    }),
  pay: (id: string, amount: number) =>
    request<Claim>("POST", `/api/claims/${id}/payment`, { amount }),
};

export function message(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong";
}
