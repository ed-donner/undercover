export type Status =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";

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

export interface QueueRun {
  waiting: number;
}
