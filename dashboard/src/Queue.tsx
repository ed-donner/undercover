import { useState } from "react";
import { getRunStatus, listClaims, startQueueRun } from "./api";
import type { ClaimState, ClaimSummary, RunStatus } from "./api";
import { decisionLabel, errorText, money, sentence } from "./format";
import { useData } from "./hooks";
import { StateBadge } from "./StateBadge";

interface QueueData {
  claims: ClaimSummary[];
  run: RunStatus;
}

const STATES: ClaimState[] = [
  "waiting",
  "in progress",
  "waiting for sign-off",
  "decided",
];

const load = async (): Promise<QueueData> => {
  const [claims, run] = await Promise.all([listClaims(), getRunStatus()]);
  return { claims, run };
};

const keepFresh = ({ claims, run }: QueueData) =>
  run.active || claims.some((claim) => claim.state === "in progress");

export function Queue() {
  const { data, error, reload } = useData(load, keepFresh);
  const [problem, setProblem] = useState<string>();

  if (!data) return <p>{error ?? "Loading the queue"}</p>;
  const { claims, run } = data;
  const count = (state: ClaimState) =>
    claims.filter((claim) => claim.state === state).length;

  const start = () => {
    startQueueRun()
      .then(reload)
      .catch((cause: unknown) => {
        setProblem(errorText(cause));
      });
  };

  return (
    <>
      <div className="heading">
        <h1>Claims queue</h1>
        <button
          type="button"
          onClick={start}
          disabled={run.active || count("waiting") === 0}
        >
          Run the queue
        </button>
      </div>
      {problem && <p className="alert">{problem}</p>}
      <ul className="counts">
        {STATES.map((state) => (
          <li key={state} className="panel">
            <span className="number">{count(state)}</span>
            <StateBadge state={state} />
          </li>
        ))}
      </ul>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th className="amount">Claimed</th>
              <th>State</th>
              <th>Decision</th>
              <th className="amount">Payout</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td className="mono">
                  <a href={`#/claims/${claim.claim_id}`}>{claim.claim_id}</a>
                </td>
                <td>{claim.customer_name}</td>
                <td>{sentence(claim.claim_type)}</td>
                <td className="amount mono">{money(claim.amount_claimed)}</td>
                <td>
                  <StateBadge state={claim.state} />
                </td>
                <td>{claim.decision ? decisionLabel[claim.decision] : "-"}</td>
                <td className="amount mono">
                  {claim.payout === null ? "-" : money(claim.payout)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
