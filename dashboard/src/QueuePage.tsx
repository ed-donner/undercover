import { useEffect, useState } from "react";
import {
  getJson,
  label,
  money,
  type ClaimRow,
  type Run,
  type Todo,
} from "./api";

const POLL_MS = 2000;
const TODO_STATES: Todo["state"][] = [
  "todo",
  "in_progress",
  "done",
  "left_for_handler",
];

export function QueuePage() {
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const load = () => {
      Promise.all([
        getJson<ClaimRow[]>("/api/claims"),
        getJson<Run | null>("/api/runs/current"),
      ])
        .then(([nextClaims, nextRun]) => {
          setClaims(nextClaims);
          setRun(nextRun);
          setFailed(false);
        })
        .catch(() => {
          setFailed(true);
        });
    };
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, []);

  return (
    <>
      {failed && <p role="alert">The queue could not be loaded.</p>}
      <section className="panel">
        <h2>Current run</h2>
        {run === null ? (
          <p>No run yet.</p>
        ) : (
          <>
            <p>
              Run {run.run_id}, {run.status}, cap {run.cap}
              {run.claim_id ? `, claim ${run.claim_id}` : ""}
            </p>
            {run.summary && <p className="summary">{run.summary}</p>}
            <h3>To-do list</h3>
            {run.todos.length === 0 ? (
              <p>The agent has not written a to-do list yet.</p>
            ) : (
              <ul className="todos">
                {TODO_STATES.map((state) =>
                  run.todos
                    .filter((todo) => todo.state === state)
                    .map((todo) => (
                      <li key={todo.text} className={`state-${state}`}>
                        <span className="tag">{label(state)}</span> {todo.text}
                      </li>
                    )),
                )}
              </ul>
            )}
          </>
        )}
      </section>
      <section className="panel">
        <h2>Claims</h2>
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Type</th>
              <th>Claimed</th>
              <th>Status</th>
              <th>Payout</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td>
                  <a href={`#/claims/${claim.claim_id}`} className="mono">
                    {claim.claim_id}
                  </a>
                </td>
                <td>{label(claim.claim_type)}</td>
                <td className="mono">{money(claim.amount_claimed)}</td>
                <td>
                  <span className={`tag status-${claim.status}`}>
                    {label(claim.status)}
                  </span>
                </td>
                <td className="mono">
                  {claim.payout === null ? "" : money(claim.payout)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
