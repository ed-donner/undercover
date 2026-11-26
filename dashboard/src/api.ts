export type Status = "waiting" | "in_progress" | "awaiting_signoff" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  decision: DecisionKind | null;
  payout: number | null;
}

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

export interface Decision {
  decision: DecisionKind;
  payout: number;
  reason: string;
  policy_section: string;
}

export interface Payment {
  amount: number;
  signed_off_by: string | null;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  customer_name: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: Document[];
  status: Status;
  decision: Decision | null;
  payment: Payment | null;
}

export interface Policy {
  policy_id: string;
  plan: { name: string; deductible: number };
  add_ons: { add_on: string; name: string }[];
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface Step {
  id: number;
  text: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok)
    throw new Error(`${path} returned ${String(response.status)}`);
  return (await response.json()) as T;
}

export const api = {
  claims: () => request<ClaimSummary[]>("/api/claims"),
  claim: (id: string) => request<Claim>(`/api/claims/${id}`),
  policy: (id: string) => request<Policy>(`/api/claims/${id}/policy`),
  steps: (id: string) => request<Step[]>(`/api/claims/${id}/steps`),
  instructions: () => request<{ text: string }>("/api/instructions"),
  handlers: () => request<Handler[]>("/api/handlers"),
  signOff: (id: string, handlerId: string) =>
    request<Claim>(`/api/claims/${id}/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ handler_id: handlerId }),
    }),
};
