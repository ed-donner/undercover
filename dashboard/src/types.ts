export type QueueStatus =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";

export interface QueueEntry {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: QueueStatus;
  needs_handler: boolean;
  handler_reason: string;
  failures: number;
}

export interface Decision {
  run_id: string;
  outcome: "approve" | "decline" | "refer";
  payout: number;
  calculation: string;
  explanation: string;
  policy_sections: number[];
  manual_version: string | null;
  manual_sections: number[];
  recorded_at: string;
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
  items: { description: string; category: string; amount: number }[];
  amount_claimed: number;
  documents: { name: string; type: string; content: string }[];
  status: QueueStatus;
  needs_handler: boolean;
  handler_reason: string;
  failures: number;
  decision: Decision | null;
  sign_off: { handler_id: string; signed_at: string } | null;
  payment: { amount: number; paid_at: string } | null;
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
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address: Record<string, string>;
  customer_since: string;
  previous_claims: {
    claim_id: string;
    filed_on: string;
    incident_date: string;
    claim_type: string;
    summary: string;
    outcome: string;
    amount_paid: number;
  }[];
}

export interface PlanDetails {
  plan: Record<string, string | number> & { plan: string; name: string };
  add_ons: { add_on: string; name: string; effect: string }[];
  deductible_applies_to: string[];
  electronics_per_item_limit: number;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface Run {
  run_id: string;
  claim_id: string;
  thread_id: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface ActivityEvent {
  sequence: number;
  run_id: string;
  kind: string;
  label: string;
  created_at: string;
}

export interface Workspace {
  claim: Claim;
  policy: Policy;
  customer: Customer;
  plan: PlanDetails;
  handlers: Handler[];
  runs: Run[];
  events: ActivityEvent[];
  reads: SourceRead[];
}

export type TaskState = "todo" | "in_progress" | "done" | "needs_handler";

export interface AgentTask {
  task_id: string;
  claim_id: string;
  state: TaskState;
  reason: string;
  admitted: boolean;
}

export interface AgentRun {
  run_id: string;
  status: "running" | "completed" | "failed";
  max_claims: number;
  summary: string;
  error: string | null;
  tasks: AgentTask[];
}

export interface SectionInfo {
  document_id: string;
  version: string;
  section: number;
  title: string;
}

export interface SectionText extends SectionInfo {
  text: string;
}

export interface SourceRead extends SectionText {
  sequence: number;
  run_id: string;
  read_at: string;
}
