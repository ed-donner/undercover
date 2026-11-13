import { money, statuses, words } from "./display";
import type { QueueEntry } from "./types";

export function ClaimCard({
  claim,
  selected,
  select,
}: {
  readonly claim: QueueEntry;
  readonly selected: boolean;
  readonly select: (id: string) => void;
}) {
  return (
    <button
      className={`claim-card ${selected ? "selected" : ""}`}
      aria-pressed={selected}
      onClick={() => {
        select(claim.claim_id);
      }}
    >
      <span className="card-top">
        <span className="mono">{claim.claim_id}</span>
        <span className={`status ${claim.status}`}>
          {statuses[claim.status]}
        </span>
        {claim.needs_handler && (
          <span className="handler-label">Handler review</span>
        )}
      </span>
      <strong>{claim.customer_name}</strong>
      <span className="claim-summary">{claim.summary}</span>
      <span className="card-bottom">
        <span>{words(claim.claim_type)}</span>
        <span className="mono">{money(claim.amount_claimed)}</span>
      </span>
    </button>
  );
}
