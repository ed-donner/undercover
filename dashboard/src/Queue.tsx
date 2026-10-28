import { useState } from "react";
import { api } from "./api";
import { Badge } from "./Badge";
import {
  DECISION_LABELS,
  money,
  STATUS_LABELS,
  STATUSES,
  words,
} from "./format";
import { useAction, useLoad } from "./hooks";

export function Queue() {
  const [queueStarted, setQueueStarted] = useState(false);
  const {
    data: claims,
    error,
    refresh,
  } = useLoad(api.claims, (loaded) =>
    Boolean(
      loaded?.some(
        (claim) =>
          claim.status === "in_progress" ||
          (queueStarted && claim.status === "waiting"),
      ),
    ),
  );
  const run = useAction();
  const waiting = claims?.some((claim) => claim.status === "waiting") ?? false;

  const runQueue = () =>
    run.act(async () => {
      await api.runQueue();
      setQueueStarted(true);
      refresh();
    });

  if (error) return <p role="alert">{error}</p>;
  if (!claims) return <p>Loading the queue...</p>;

  return (
    <>
      <div className="page-head">
        <h1>Claims queue</h1>
        <button
          type="button"
          onClick={() => void runQueue()}
          disabled={!waiting || run.busy}
        >
          Run the queue
        </button>
      </div>
      {run.error && <p role="alert">{run.error}</p>}
      <ul className="counts" aria-label="Claims by state">
        {STATUSES.map((status) => (
          <li key={status} className="panel count">
            <span className={`dot dot-${status}`} />
            <span className="count-label">{STATUS_LABELS[status]}</span>
            <span className="count-number">
              {claims.filter((claim) => claim.status === status).length}
            </span>
          </li>
        ))}
      </ul>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col" className="wide">
                Type
              </th>
              <th scope="col" className="wide">
                Summary
              </th>
              <th scope="col" className="number">
                Claimed
              </th>
              <th scope="col" className="wide">
                Submitted
              </th>
              <th scope="col">State</th>
              <th scope="col">Decision</th>
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
                <td className="wide">{words(claim.claim_type)}</td>
                <td className="wide">{claim.summary}</td>
                <td className="number mono">{money(claim.amount_claimed)}</td>
                <td className="wide mono">{claim.submitted_on}</td>
                <td>
                  <Badge status={claim.status} />
                </td>
                <td>
                  {claim.decision && DECISION_LABELS[claim.decision]}
                  {claim.decision === "approve" && (
                    <span className="mono"> {money(claim.payout ?? 0)}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
