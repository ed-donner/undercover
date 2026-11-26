import type { ClaimSummary, Status } from "../api";
import { api } from "../api";
import { claimType, money, statusLabels } from "../format";
import { StatusBadge } from "../StatusBadge";
import { useData } from "../useData";

const order: Status[] = [
  "waiting",
  "in_progress",
  "awaiting_signoff",
  "decided",
];

function Counts({ claims }: Readonly<{ claims: ClaimSummary[] }>) {
  return (
    <section className="counts" aria-label="Claims by state">
      {order.map((status) => (
        <div key={status} className={`panel count ${status}`}>
          <span className="number">
            {claims.filter((c) => c.status === status).length}
          </span>
          <span>{statusLabels[status]}</span>
        </div>
      ))}
    </section>
  );
}

export function Queue() {
  const { data: claims, error } = useData(api.claims);
  if (error) return <p role="alert">Could not load the queue: {error}</p>;
  if (!claims) return <p>Loading the queue</p>;

  return (
    <>
      <h1>Claims queue</h1>
      <Counts claims={claims} />
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th>Summary</th>
              <th className="amount">Claimed</th>
              <th className="amount">Payout</th>
              <th>State</th>
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
                <td>{claimType(claim.claim_type)}</td>
                <td>{claim.summary}</td>
                <td className="amount mono">{money(claim.amount_claimed)}</td>
                <td className="amount mono">
                  {claim.payout === null ? "" : money(claim.payout)}
                </td>
                <td>
                  <StatusBadge status={claim.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
