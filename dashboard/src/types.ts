export type QueueStatus =
  "waiting" | "in_progress" | "waiting_for_agent_review" | "decided";
export type Outcome = "approve" | "decline" | "request_information";

export interface QueueItem {
  request_id: string;
  order_id: string;
  customer_name: string;
  type: string;
  created_at: string;
  status: QueueStatus;
  attempts: number;
  recommendation: Recommendation | null;
  review: Review | null;
}

export interface Review {
  outcome: Outcome;
  notes: string;
  reviewed_at: string;
}

export interface Recommendation {
  outcome: Outcome;
  rationale: string;
  policy_citations: string[];
  next_action: string;
  priority_human_review: boolean;
}

export interface SupportRequest {
  request_id: string;
  type: string;
  created_at: string;
  customer_message: string;
  requested_scope: string;
  evidence: { type: string; reference: string; description: string }[];
}

export interface RequestDetail {
  request: SupportRequest;
  customer: { customer_id: string; name: string };
  order: {
    order_id: string;
    placed_at: string;
    fulfillment_status: string;
    payment_status: string;
    payment_method: string;
    delivery_window: { start: string; end: string } | null;
    delivered_at?: string;
    items: {
      name: string;
      sku: string;
      quantity: number;
      unit_price: number;
      line_total: number;
    }[];
    subtotal: number;
    delivery_fee: number;
    total: number;
  };
  status: QueueStatus;
  attempts: number;
  recommendation: Recommendation | null;
  review: Review | null;
  steps: { stage: string; message: string; created_at: string }[];
}

export type TodoStatus = "to_do" | "in_progress" | "done" | "left_for_support";

export interface Todo {
  request_id: string;
  title: string;
  status: TodoStatus;
}

export interface Run {
  run_id: string;
  cap: number;
  status: "running" | "finished" | "failed";
  started_at: string;
  finished_at: string | null;
  summary: string | null;
  todos: Todo[];
}

export interface Instructions {
  queue: string;
  request: string;
}
