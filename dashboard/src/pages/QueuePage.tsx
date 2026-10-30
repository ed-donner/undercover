import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { fetchClaims, fetchCurrentRun } from "../api";
import { RunItemBadge } from "../components/RunItemBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatMoney } from "../money";
import type { ClaimSummary, Run } from "../types";
import { usePolling } from "../usePolling";

export function QueuePage() {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [run, setRun] = useState<Run | null>(null);

  const load = useCallback(() => {
    void fetchClaims().then(setClaims);
    void fetchCurrentRun().then(setRun);
  }, []);

  useEffect(load, [load]);
  usePolling(load, !run?.finished_on);

  return (
    <main className="panel">
      <h1>The claims queue</h1>

      {run && (
        <>
          <h2>The current run</h2>
          <ul>
            {run.items.map((item) => (
              <li key={item.claim_id}>
                {item.claim_id} <RunItemBadge status={item.status} />
                {item.note ? ` — ${item.note}` : ""}
              </li>
            ))}
          </ul>
          {run.summary && <p>{run.summary}</p>}
        </>
      )}

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
              <td>{formatMoney(claim.amount_claimed)}</td>
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
