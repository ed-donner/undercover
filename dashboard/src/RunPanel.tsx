import { useState } from "react";
import { api, message, type Run } from "./api";
import { time } from "./format";
import { RunChip, TodoChip } from "./StatusChip";
import { useGet } from "./useGet";

const REFRESH_MS = 2000;
const DEFAULT_CAP = 5;

function scope(run: Run) {
  if (run.claim_id) return `${run.claim_id} only`;
  return `The queue, up to ${String(run.cap)} ${run.cap === 1 ? "claim" : "claims"}`;
}

function Times({ run }: Readonly<{ run: Run }>) {
  return (
    <span className="muted">
      Started {time(run.started_at)}
      {run.finished_at && `, ended ${time(run.finished_at)}`}
    </span>
  );
}

function Todos({ run }: Readonly<{ run: Run }>) {
  if (run.todos.length === 0) {
    return run.status === "running" ? (
      <p className="muted">The agent is planning its work...</p>
    ) : null;
  }
  return (
    <ul className="todos" aria-label="To-do list">
      {run.todos.map((todo) => (
        <li key={todo.claim_id}>
          <a className="mono" href={`#/claims/${todo.claim_id}`}>
            {todo.claim_id}
          </a>
          <span>{todo.content}</span>
          <TodoChip status={todo.status} />
        </li>
      ))}
    </ul>
  );
}

export function RunPanel() {
  const { data: run, reload } = useGet<Run | null>(
    "/api/runs/latest",
    REFRESH_MS,
  );
  const [cap, setCap] = useState(DEFAULT_CAP);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const running = run?.status === "running";

  const start = async () => {
    setBusy(true);
    setError(undefined);
    try {
      await api.startRun(cap);
      reload();
    } catch (problem) {
      setError(message(problem));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="Current run">
      <div className="run-head">
        <h2>Current run</h2>
        {run && <RunChip status={run.status} />}
        {run && <span>{scope(run)}</span>}
        {run && <Times run={run} />}
        <div className="run-start">
          <label htmlFor="cap">Claims to work</label>
          <input
            id="cap"
            type="number"
            min={1}
            value={cap}
            onChange={(event) => {
              setCap(Number(event.target.value));
            }}
          />
          <button
            type="button"
            disabled={busy || running || cap < 1}
            onClick={() => void start()}
          >
            Run the queue
          </button>
        </div>
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {run === null && <p className="muted">The agent has not run yet.</p>}
      {run && <Todos run={run} />}
      {run?.summary && <p>{run.summary}</p>}
      {run?.problem && <p className="alert">{run.problem}</p>}
    </section>
  );
}
