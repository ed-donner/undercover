import { useEffect, useState } from "react";

export type Status = "waiting" | "in_progress" | "awaiting_signoff" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";
export type StepKind = "tool_call" | "tool_result" | "message" | "error";

export interface ClaimSummary {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  customer_name: string;
  claim_type: string;
  submitted_on: string;
  summary: string;
  amount_claimed: number;
  status: Status;
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

export interface Decision {
  decision: DecisionKind;
  payout: number;
  calculation: string;
  reasons: string;
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

export interface Claim extends ClaimSummary {
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: ClaimDocument[];
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
  plan_details: { name: string; deductible: number };
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  step_id: number;
  kind: StepKind;
  content: string;
  created_at: string;
}

export interface Text {
  text: string;
}

// Each endpoint carries the type of its reply, so reads are typed end to end.
export interface Endpoint<T> {
  url: string;
  reply?: T;
}

export const endpoints = {
  claims: (): Endpoint<ClaimSummary[]> => ({ url: "/api/claims" }),
  claim: (id: string): Endpoint<Claim> => ({ url: `/api/claims/${id}` }),
  steps: (id: string): Endpoint<Step[]> => ({ url: `/api/claims/${id}/steps` }),
  policy: (id: string): Endpoint<Policy> => ({ url: `/api/policies/${id}` }),
  handlers: (): Endpoint<Handler[]> => ({ url: "/api/handlers" }),
  instructions: (): Endpoint<Text> => ({ url: "/api/instructions" }),
};

async function parse(response: Response): Promise<unknown> {
  if (!response.ok) {
    const body = (await response.json()) as { detail: string };
    throw new Error(body.detail);
  }
  return response.json();
}

export async function getJson<T>(endpoint: Endpoint<T>): Promise<T> {
  return (await parse(await fetch(endpoint.url))) as T;
}

export async function postJson(path: string, body: unknown): Promise<void> {
  await parse(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

interface Loaded<T> {
  url: string | null;
  data?: T;
  error?: string;
}

export interface ApiState<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

export function useApi<T>(
  endpoint: Endpoint<T> | null,
  pollMs = 0,
): ApiState<T> {
  const url = endpoint?.url ?? null;
  const [loaded, setLoaded] = useState<Loaded<T>>({ url });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!url) return;
    let active = true;
    const load = () => {
      getJson<T>({ url }).then(
        (data) => {
          if (active) setLoaded({ url, data });
        },
        (error: unknown) => {
          if (active) {
            const message =
              error instanceof Error ? error.message : String(error);
            setLoaded({ url, error: message });
          }
        },
      );
    };
    load();
    const timer = pollMs ? setInterval(load, pollMs) : undefined;
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [url, pollMs, version]);

  const current = loaded.url === url ? loaded : { url };
  return {
    data: current.data,
    error: current.error,
    reload: () => {
      setVersion((v) => v + 1);
    },
  };
}
