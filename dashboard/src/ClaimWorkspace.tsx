import { useCallback } from "react";
import { api, useResource } from "./api";
import { ClaimEvidence, CustomerPanel, PolicyPanel } from "./ClaimEvidence";
import { ActivityPanel, ClaimActions, DecisionPanel } from "./DecisionPanel";
import { money, words } from "./display";
import type {
  ActivityEvent,
  Claim,
  Customer,
  Handler,
  PlanDetails,
  Policy,
  Run,
  Workspace,
} from "./types";

async function loadWorkspace(id: string): Promise<Workspace> {
  const claim = await api<Claim>(`/claims/${id}`);
  const [policy, customer, handlers, runs, events] = await Promise.all([
    api<Policy>(`/policies/${claim.policy_id}`),
    api<Customer>(`/customers/${claim.customer_id}`),
    api<Handler[]>("/handlers"),
    api<Run[]>(`/claims/${id}/runs`),
    api<ActivityEvent[]>(`/claims/${id}/events`),
  ]);
  const plan = await api<PlanDetails>(`/plans/${policy.plan}`);
  return { claim, policy, customer, handlers, runs, events, plan };
}

export function ClaimWorkspace({
  id,
  onChange,
}: {
  readonly id: string;
  readonly onChange: () => void;
}) {
  const load = useCallback(() => loadWorkspace(id), [id]);
  const resource = useResource(load);
  const data = resource.data;
  return (
    <div className="workspace" aria-label="Claim workspace">
      {resource.error && (
        <div className="error" role="alert">
          {resource.error}{" "}
          <button onClick={resource.reload}>Retry details</button>
        </div>
      )}
      {!data && !resource.error && <p role="status">Loading claim…</p>}
      {data && (
        <>
          <header className="claim-header">
            <div>
              <span className="eyebrow mono">
                {data.claim.claim_id} · {words(data.claim.claim_type)}
              </span>
              <h2>{data.customer.name}</h2>
              <p>{data.claim.summary}</p>
            </div>
            <div className="claimed-total">
              <span className="eyebrow">Amount claimed</span>
              <strong>{money(data.claim.amount_claimed)}</strong>
              <span>USD</span>
            </div>
          </header>
          <ClaimActions
            claim={data.claim}
            handlers={data.handlers}
            runs={data.runs}
            onChange={() => {
              resource.reload();
              onChange();
            }}
          />
          <div className="workspace-columns">
            <div className="main-column">
              <ClaimEvidence claim={data.claim} />
              <PolicyPanel policy={data.policy} plan={data.plan} />
              <CustomerPanel customer={data.customer} />
            </div>
            <div className="review-column">
              <DecisionPanel claim={data.claim} />
              <ActivityPanel events={data.events} runs={data.runs} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const loadInstructions = () => api<{ text: string }>("/instructions");
const loadWording = () => api<{ text: string; version: string }>("/wording");

export function Instructions() {
  const instructions = useResource(loadInstructions, 30000);
  const wording = useResource(loadWording, 30000);
  return (
    <div className="instructions-view">
      <header className="claim-header">
        <div>
          <span className="eyebrow">UnderCover Agent</span>
          <h2>Instructions & policy wording</h2>
          <p>
            Read only. The same instructions and wording the agent reads through
            the API.
          </p>
        </div>
      </header>
      {instructions.error && (
        <p className="error" role="alert">
          {instructions.error}{" "}
          <button onClick={instructions.reload}>Retry instructions</button>
        </p>
      )}
      <section className="panel">
        <h3>Agent instructions</h3>
        {instructions.data ? (
          <pre className="wording">{instructions.data.text}</pre>
        ) : (
          <p role="status">Loading instructions…</p>
        )}
      </section>
      {wording.error && (
        <p className="error" role="alert">
          {wording.error}{" "}
          <button onClick={wording.reload}>Retry wording</button>
        </p>
      )}
      <section className="panel">
        <h3>Policy wording {wording.data?.version}</h3>
        {wording.data ? (
          <pre className="wording">{wording.data.text}</pre>
        ) : (
          <p role="status">Loading policy wording…</p>
        )}
      </section>
    </div>
  );
}
