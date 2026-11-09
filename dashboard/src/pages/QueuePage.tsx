import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { fetchClaims, fetchCurrentRun } from "../api";
import { RunItemBadge } from "../components/RunItemBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatMoney } from "../money";
import type { ClaimSummary, Run } from "../types";
import { usePolling } from "../usePolling";

const TOTALS = [
  ["Waiting", "waiting"],
  ["In progress", "in progress"],
  ["Waiting for sign-off", "waiting for sign-off"],
  ["Decided", "decided"],
] as const;

export function QueuePage() {
  const [claims, setClaims] = useState<ClaimSummary[] | null>(null);
  const [run, setRun] = useState<Run | null | undefined>(undefined);

  const load = useCallback(() => {
    void fetchClaims().then(setClaims);
    void fetchCurrentRun().then(setRun);
  }, []);

  useEffect(load, [load]);
  usePolling(load, !run?.finished_on);

  const count = (status: string) =>
    claims ? claims.filter((claim) => claim.status === status).length : "–";
  const leftForHandler =
    run === undefined
      ? "–"
      : (run?.items.filter((item) => item.status === "left for a handler")
          .length ?? 0);

  return (
    <main className="panel">
      <h1>The claims queue</h1>

      <dl className="totals">
        {TOTALS.map(([label, status]) => (
          <div key={status}>
            <dt>{label}</dt>
            <dd>{count(status)}</dd>
          </div>
        ))}
        <div>
          <dt>Left for a handler</dt>
          <dd>{leftForHandler}</dd>
        </div>
      </dl>

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
          {(claims ?? []).map((claim) => (
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
