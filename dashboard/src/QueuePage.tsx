import { listClaims, type QueueEntry } from "./api";
import { DecisionLabel, StatusBadge, Unreachable } from "./common";
import { formatDate, humanize, money, STATUSES } from "./format";
import { POLL_MS, useApi } from "./hooks";
import { RunPanel } from "./RunPanel";

export function QueuePage() {
  const { data: claims, failed } = useApi(listClaims, POLL_MS);
  return (
    <>
      <h1>Claims queue</h1>
      {failed && <Unreachable />}
      {!claims && !failed && <p className="muted">Loading the queue.</p>}
      {claims && <StatusCounts claims={claims} />}
      <RunPanel />
      {claims && <QueueTable claims={claims} />}
    </>
  );
}

function StatusCounts({ claims }: Readonly<{ claims: QueueEntry[] }>) {
  return (
    <section className="counts" aria-label="Claims by status">
      {STATUSES.map((status) => (
        <div className="panel count" key={status}>
          <span className="count-number">
            {claims.filter((claim) => claim.status === status).length}
          </span>
          <StatusBadge status={status} />
        </div>
      ))}
    </section>
  );
}

function QueueTable({ claims }: Readonly<{ claims: QueueEntry[] }>) {
  return (
    <section className="panel table-panel" aria-label="Claims">
      <table>
        <thead>
          <tr>
            <th scope="col">Claim</th>
            <th scope="col">Customer</th>
            <th scope="col">What happened</th>
            <th scope="col">Submitted</th>
            <th scope="col" className="number">
              Claimed
            </th>
            <th scope="col">Status</th>
            <th scope="col">Decision</th>
            <th scope="col" className="number">
              Payout
            </th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>
                <a className="mono" href={`#/claims/${claim.claim_id}`}>
                  {claim.claim_id}
                </a>
              </td>
              <td>{claim.customer_name}</td>
              <td>
                {claim.summary}
                <span className="muted small block">
                  {humanize(claim.claim_type)}
                </span>
              </td>
              <td className="nowrap">{formatDate(claim.submitted_on)}</td>
              <td className="number">{money(claim.amount_claimed)}</td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
              <td>
                {claim.decision && <DecisionLabel decision={claim.decision} />}
              </td>
              <td className="number">
                {claim.decision === "approve" && claim.payout !== null
                  ? money(claim.payout)
                  : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
