import { useEffect, useState } from "react";
import { Link } from "react-router";
import { fetchClaims } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { ClaimSummary } from "../types";

export function QueuePage() {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);

  useEffect(() => {
    void fetchClaims().then(setClaims);
  }, []);

  return (
    <main className="panel">
      <h1>The claims queue</h1>
      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Type</th>
            <th>Summary</th>
            <th>Amount claimed</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>
                <Link to={`/claims/${claim.claim_id}`}>{claim.claim_id}</Link>
              </td>
              <td>{claim.claim_type}</td>
              <td>{claim.summary}</td>
              <td>${claim.amount_claimed.toFixed(2)}</td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
