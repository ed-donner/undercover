export type ClaimStatus =
  "waiting" | "in_progress" | "awaiting_signoff" | "decided" | "for_handler";

export type TodoStatus = "todo" | "in_progress" | "done" | "for_handler";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: ClaimStatus;
  decision: string | null;
  payout: number | null;
  paid: number | null;
}

export interface Step {
  kind: string;
  text: string;
  created_at: string;
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

export interface Claim extends ClaimSummary {
  story: string;
  incident_location: string;
  incident_date: string;
  items: ClaimItem[];
  documents: ClaimDocument[];
  reason: string | null;
  policy_section: string | null;
  attempts: number;
  signed_off_by: string | null;
  steps: Step[];
}

export interface Todo {
  text: string;
  status: TodoStatus;
}

export interface Run {
  id: number;
  limit: number;
  summary: string | null;
  finished: boolean;
  todos: Todo[];
  claims: string[];
}

export interface Handler {
  handler_id: string;
  name: string;
}

export interface Instructions {
  queue: string;
  claim: string;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${String(response.status)}`);
  return (await response.json()) as T;
}

export async function post(path: string, body: object): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path}: ${String(response.status)}`);
}

export function money(amount: number | null): string {
  if (amount === null) return "-";
  return amount.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export const STATUS_LABELS: Record<ClaimStatus | TodoStatus, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  awaiting_signoff: "Waiting for sign-off",
  decided: "Decided",
  for_handler: "For a handler",
  todo: "To do",
  done: "Done",
};
