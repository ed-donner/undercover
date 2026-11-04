export interface ClaimRow {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: string;
  attempts: number;
  decision: string | null;
  payout: number | null;
}

export interface Todo {
  text: string;
  state: "todo" | "in_progress" | "done" | "left_for_handler";
  claim_id: string | null;
}

export interface Run {
  run_id: number;
  cap: number;
  claim_id: string | null;
  status: string;
  summary: string | null;
  todos: Todo[];
}

export interface ClaimDetail {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: string;
  attempts: number;
  decision: {
    decision: string;
    payout: number;
    section: string;
    reason: string;
  } | null;
  payment: { amount: number; paid_at: string } | null;
  steps: { tool: string; summary: string; at: string }[];
  reads: { document: string; number: number; title: string }[];
}

export interface Instructions {
  queue_runner: string;
  claim: string;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${String(response.status)}`);
  return (await response.json()) as T;
}

export const money = (amount: number): string =>
  amount.toLocaleString("en-US", { style: "currency", currency: "USD" });

export const label = (text: string): string => {
  const words = text.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
};
