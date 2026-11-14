import type { ClaimSummary } from "./api";
import { date, label, money, STATUS_LABELS, STATUSES } from "./format";
import { StatusChip } from "./StatusChip";
import { useGet } from "./useGet";

const REFRESH_MS = 2000;

export function Queue() {
  const { data: claims, error } = useGet<ClaimSummary[]>(
    "/api/claims",
    REFRESH_MS,
  );

  if (!claims) {
    return error ? (
      <p className="alert">Could not load the queue.</p>
    ) : (
      <p className="muted">Loading the queue...</p>
    );
  }

  return (
    <>
      <h1>Claims queue</h1>
      <div className="counts">
        {STATUSES.map((status) => (
          <div className="count" key={status}>
            <StatusChip status={status} />
            <strong aria-label={`${STATUS_LABELS[status]} count`}>
              {claims.filter((claim) => claim.status === status).length}
            </strong>
          </div>
        ))}
      </div>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Summary</th>
              <th>Type</th>
              <th>Submitted</th>
              <th className="amount">Claimed</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td className="mono nowrap">
                  <a href={`#/claims/${claim.claim_id}`}>{claim.claim_id}</a>
                </td>
                <td>{claim.summary}</td>
                <td>{label(claim.claim_type)}</td>
                <td className="nowrap">{date(claim.submitted_on)}</td>
                <td className="amount mono">{money(claim.amount_claimed)}</td>
                <td>
                  <StatusChip status={claim.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
