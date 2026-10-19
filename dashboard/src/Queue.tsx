import { useState } from "react";
import { getLatestRun, listClaims, runClaim, runQueue } from "./api";
import {
  claimType,
  decisionText,
  money,
  STATUS_LABELS,
  STATUSES,
} from "./format";
import { RunPanel } from "./RunPanel";
import { StatusChip } from "./StatusChip";
import type { Status } from "./types";
import { usePolled } from "./usePolled";

const REFRESH_MS = 3000;

export function Queue() {
  const { data: claims, error, reload } = usePolled(listClaims, REFRESH_MS);
  const { data: run } = usePolled(getLatestRun, REFRESH_MS);
  const [trial, setTrial] = useState(5);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [failed, setFailed] = useState(false);

  if (!claims) {
    return (
      <p role={error ? "alert" : "status"}>
        {error ? "The queue could not be loaded." : "Loading the queue"}
      </p>
    );
  }

  const count = (status: Status) =>
    claims.filter((claim) => claim.status === status).length;
  const shown =
    filter === "all"
      ? claims
      : claims.filter((claim) => claim.status === filter);

  const running = run?.status === "running";
  const start = (action: () => Promise<unknown>) => {
    setFailed(false);
    action()
      .then(reload)
      .catch(() => {
        setFailed(true);
      });
  };

  return (
    <>
      <div className="toolbar">
        <h1>Claims queue</h1>
        <div className="row">
          <label className="trial">
            Claims in a trial
            <input
              type="number"
              min={1}
              value={trial}
              onChange={(event) => {
                setTrial(Number(event.target.value));
              }}
            />
          </label>
          <button
            disabled={count("waiting") === 0 || running || trial < 1}
            onClick={() => {
              start(() => runQueue(trial));
            }}
          >
            Run trial
          </button>
          <button
            className="primary"
            disabled={count("waiting") === 0 || running}
            onClick={() => {
              start(() => runQueue(count("waiting")));
            }}
          >
            Run agent on all waiting claims
          </button>
        </div>
      </div>
      {run && <RunPanel run={run} />}
      {failed && (
        <p role="alert" className="alert">
          The agent could not be started.
        </p>
      )}
      <div className="filters" role="group" aria-label="Filter by status">
        <button
          aria-pressed={filter === "all"}
          onClick={() => {
            setFilter("all");
          }}
        >
          All <span className="mono">{claims.length}</span>
        </button>
        {STATUSES.map((status) => (
          <button
            key={status}
            aria-pressed={filter === status}
            onClick={() => {
              setFilter(status);
            }}
          >
            {STATUS_LABELS[status]}{" "}
            <span className="mono">{count(status)}</span>
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="panel empty">No claims with this status.</p>
      ) : (
        <div className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>Claim</th>
                <th>Customer</th>
                <th>Type</th>
                <th>Summary</th>
                <th className="number">Claimed</th>
                <th>Status</th>
                <th>Decision</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((claim) => (
                <tr key={claim.claim_id}>
                  <td data-label="Claim">
                    <a className="mono" href={`#/claims/${claim.claim_id}`}>
                      {claim.claim_id}
                    </a>
                  </td>
                  <td data-label="Customer">{claim.customer_name}</td>
                  <td data-label="Type">{claimType(claim.claim_type)}</td>
                  <td data-label="Summary">{claim.summary}</td>
                  <td data-label="Claimed" className="number mono">
                    {money(claim.amount_claimed)}
                  </td>
                  <td data-label="Status">
                    <StatusChip status={claim.status} />
                  </td>
                  <td data-label="Decision">
                    {decisionText(claim.decision, claim.payout)}
                  </td>
                  <td className="actions">
                    {claim.status === "waiting" && (
                      <button
                        onClick={() => {
                          start(() => runClaim(claim.claim_id));
                        }}
                      >
                        Run agent
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
