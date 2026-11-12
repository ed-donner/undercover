export type ClaimStatus =
  "waiting" | "in progress" | "waiting for sign-off" | "decided";

export type Decision = "approve" | "decline" | "refer";

/** Amounts are whole cents. */
export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: ClaimStatus;
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

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
  };
  travelers: string[];
  status: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
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
  status: ClaimStatus;
  decision: Decision | null;
  payout: number | null;
  reason: string | null;
  policy_reference: string | null;
  decided_on: string | null;
  over_approval_limit: number | null;
  signed_off_by: string | null;
  signed_off_on: string | null;
  paid_amount: number | null;
  paid_on: string | null;
  policy: Policy;
  customer_previous_claims: PreviousClaim[];
}

export interface Step {
  recorded_on: string;
  text: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  email: string;
  can_approve_over_limit: boolean;
}

export type RunItemStatus =
  "to do" | "in progress" | "done" | "left for a handler";

export interface RunItem {
  claim_id: string;
  status: RunItemStatus;
  attempts: number;
  note: string | null;
}

export interface Run {
  run_id: number;
  started_on: string;
  finished_on: string | null;
  summary: string | null;
  items: RunItem[];
}
