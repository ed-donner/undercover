import type { ClaimSummary, Run } from "./api";
import { money } from "./api";
import { Status } from "./Status";
import { TodoList } from "./TodoList";
import { useFetch } from "./useFetch";

const POLL_MS = 2000;

export function QueuePage() {
  const claims = useFetch<ClaimSummary[]>("/api/claims", POLL_MS).data;
  const run = useFetch<Run | null>("/api/runs/current", POLL_MS).data;

  return (
    <>
      <section className="panel">
        <h2>Current run</h2>
        {run ? (
          <>
            <p className="muted">
              Run {run.id}, up to {run.limit} claims
              {run.finished ? ", finished" : ", working"}
            </p>
            <TodoList todos={run.todos} />
            {run.summary && <p className="summary">{run.summary}</p>}
          </>
        ) : (
          <p className="muted">No run yet.</p>
        )}
      </section>
      <section className="panel">
        <h2>Queue</h2>
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Type</th>
              <th>Summary</th>
              <th className="num">Claimed</th>
              <th>Status</th>
              <th className="num">Payout</th>
            </tr>
          </thead>
          <tbody>
            {(claims ?? []).map((claim) => (
              <tr key={claim.claim_id}>
                <td className="mono">
                  <a href={`#/claims/${claim.claim_id}`}>{claim.claim_id}</a>
                </td>
                <td>{claim.claim_type.replaceAll("_", " ")}</td>
                <td>{claim.summary}</td>
                <td className="num mono">{money(claim.amount_claimed)}</td>
                <td>
                  <Status status={claim.status} />
                </td>
                <td className="num mono">{money(claim.payout)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
