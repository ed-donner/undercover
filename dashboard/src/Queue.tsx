import { endpoints, useApi } from "./api";
import { ErrorPanel, Loading, StatusBadge } from "./components";
import { STATUSES, date, label, money } from "./format";

export function Queue() {
  const { data: claims, error } = useApi(endpoints.claims(), 3000);

  if (error) return <ErrorPanel message={error} />;
  if (!claims) return <Loading what="the queue" />;

  return (
    <>
      <h1>Claims queue</h1>
      <section className="tiles" aria-label="Claims by state">
        {STATUSES.map((status) => (
          <div className="panel tile" key={status}>
            <StatusBadge status={status} />
            <span className="tile-count mono">
              {claims.filter((c) => c.status === status).length}
            </span>
          </div>
        ))}
      </section>
      <section className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">Customer</th>
              <th scope="col">Type</th>
              <th scope="col">Summary</th>
              <th scope="col" className="number">
                Claimed
              </th>
              <th scope="col">Submitted</th>
              <th scope="col">State</th>
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
                <td>{label(claim.claim_type)}</td>
                <td className="summary">{claim.summary}</td>
                <td className="number mono">{money(claim.amount_claimed)}</td>
                <td className="nowrap">{date(claim.submitted_on)}</td>
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
