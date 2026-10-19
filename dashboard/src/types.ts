export type Status =
  | "waiting"
  | "in_progress"
  | "waiting_for_sign_off"
  | "decided"
  | "needs_handler";

export type Outcome = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
  decision: Outcome | null;
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
  decision: Outcome;
  payout: number;
  explanation: string;
  policy_section: string;
  decided_at: string;
}

export interface Payment {
  amount: number;
  paid_at: string;
}

export interface SignOff {
  handler_id: string;
  handler_name: string;
  signed_at: string;
}

export interface ClaimDetail {
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
  sign_off: SignOff | null;
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
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export interface Step {
  id: number;
  kind: "tool_call" | "tool_result" | "message" | "error" | "read";
  text: string;
  created_at: string;
}

export type TodoStatus = "todo" | "in_progress" | "done" | "left_for_handler";

export interface Todo {
  text: string;
  status: TodoStatus;
}

export interface Run {
  run_id: number;
  limit: number;
  status: "running" | "finished" | "failed";
  summary: string;
  started_at: string;
  finished_at: string | null;
  todos: Todo[];
}

export interface Instructions {
  queue: string;
  claim: string;
}
