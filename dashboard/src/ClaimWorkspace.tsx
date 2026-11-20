import { useCallback } from "react";
import { claimsApi } from "./api";
import { ClaimEvidence, CustomerPanel, PolicyPanel } from "./ClaimEvidence";
import { ActivityPanel, ClaimActions, DecisionPanel } from "./DecisionPanel";
import { money, words } from "./display";
import { ClaimSources } from "./Sources";
import { useResource } from "./useResource";

export function ClaimWorkspace({
  id,
  onChange,
  runActive = false,
}: {
  readonly id: string;
  readonly onChange: () => void;
  readonly runActive?: boolean;
}) {
  const load = useCallback(() => claimsApi.workspace(id), [id]);
  const resource = useResource(load);
  const data = resource.data;
  return (
    <div className="workspace" aria-label="Claim workspace">
      {resource.error && (
        <div className="error" role="alert">
          {resource.error}
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
            runActive={runActive}
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
              <ClaimSources reads={data.reads} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
