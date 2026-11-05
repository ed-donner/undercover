export type Status =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
export type Decision = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  decision: Decision | null;
  payout: number | null;
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

export interface PlanLimits {
  plan: string;
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: Record<string, string | number>;
  travelers: string[];
  status: string;
  plan_limits: PlanLimits;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address: Record<string, string>;
  customer_since: string;
  previous_claims: PreviousClaim[];
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
  items: ClaimItem[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  decision: Decision | null;
  payout: number | null;
  reason: string | null;
  reference: string | null;
  signed_off_by: string | null;
  paid_amount: number | null;
  customer: Customer;
  policy: Policy;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  email: string;
  can_approve_over_limit: boolean;
}

export interface ClaimEvent {
  operation_id: string;
  message: string;
  created_at: string;
}

export interface PaymentResult {
  paid: boolean;
  status: Status;
}

export interface RunClaimResult {
  reply: string;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok)
    throw new Error(`${path} failed: ${String(response.status)}`);
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok)
    throw new Error(`${path} failed: ${String(response.status)}`);
  return (await response.json()) as T;
}

export function listClaims(): Promise<ClaimSummary[]> {
  return getJson("/api/claims");
}

export function getClaim(claimId: string): Promise<Claim> {
  return getJson(`/api/claims/${claimId}`);
}

export function listClaimEvents(claimId: string): Promise<ClaimEvent[]> {
  return getJson(`/api/claims/${claimId}/events`);
}

export function listHandlers(): Promise<Handler[]> {
  return getJson("/api/handlers");
}

export async function getAgentInstructions(): Promise<string> {
  const { content } = await getJson<{ content: string }>(
    "/api/agent-instructions",
  );
  return content;
}

export function runClaim(claimId: string): Promise<RunClaimResult> {
  return postJson(`/api/claims/${claimId}/run`);
}

export function signOffClaim(
  claimId: string,
  handlerId: string,
): Promise<PaymentResult> {
  return postJson(`/api/claims/${claimId}/sign-off`, { handler_id: handlerId });
}
