import type {
  ActivityEvent,
  AgentRun,
  Claim,
  Customer,
  Handler,
  PlanDetails,
  Policy,
  QueueEntry,
  Run,
  SectionInfo,
  SectionText,
  SourceRead,
  Workspace,
} from "./types";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body: unknown = await response.json();
    const detail =
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${String(response.status)}).`;
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function post(path: string, body: object): Promise<unknown> {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const id = encodeURIComponent;

export const runsApi = {
  list: () => api<AgentRun[]>("/agent-runs"),
  startQueue: (maxClaims: number | null) =>
    post("/agent-runs", { mode: "queue", max_claims: maxClaims }),
  startClaim: (claimId: string) =>
    post("/agent-runs", { mode: "claim", claim_id: claimId }),
};

export const claimsApi = {
  list: () => api<QueueEntry[]>("/claims"),
  signOff: (claimId: string, handlerId: string) =>
    post(`/claims/${id(claimId)}/sign-off`, { handler_id: handlerId }),
  pay: (claimId: string, amount: number) =>
    post(`/claims/${id(claimId)}/payment`, { amount }),
  async workspace(claimId: string): Promise<Workspace> {
    const path = `/claims/${id(claimId)}`;
    const claim = await api<Claim>(path);
    const [policy, customer, handlers, runs, events, reads] = await Promise.all(
      [
        api<Policy>(`/policies/${id(claim.policy_id)}`),
        api<Customer>(`/customers/${id(claim.customer_id)}`),
        api<Handler[]>("/handlers"),
        api<Run[]>(`${path}/runs`),
        api<ActivityEvent[]>(`${path}/events`),
        api<SourceRead[]>(`${path}/reads`),
      ],
    );
    const plan = await api<PlanDetails>(`/plans/${id(policy.plan)}`);
    return { claim, policy, customer, handlers, runs, events, reads, plan };
  },
};

export const documentsApi = {
  catalog: () => api<SectionInfo[]>("/documents"),
  section: (documentId: string, section: number) =>
    api<SectionText>(
      `/documents/${id(documentId)}/sections/${String(section)}`,
    ),
  wording: () => api<{ text: string; version: string }>("/wording"),
};

export const instructionsApi = {
  claim: () => api<{ text: string }>("/instructions/claim"),
  queue: () => api<{ text: string }>("/instructions/queue"),
};
