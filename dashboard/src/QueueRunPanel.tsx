import { useState } from "react";
import { runsApi } from "./api";
import type { AgentRun, TaskState } from "./types";

const taskLabels: Record<TaskState, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  needs_handler: "Left for a handler",
};

export function QueueRunPanel({
  runs,
  error,
  eligible,
  reload,
  select,
}: {
  readonly runs: AgentRun[] | undefined;
  readonly error: string | undefined;
  readonly eligible: number;
  readonly reload: () => void;
  readonly select: (claimId: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [startError, setStartError] = useState<string>();
  const latest = runs?.[0];
  const active = latest?.status === "running";
  const disabled = busy || active || !runs || eligible === 0;
  async function start(maxClaims: number | null) {
    setBusy(true);
    setStartError(undefined);
    try {
      await runsApi.startQueue(maxClaims);
    } catch (cause) {
      setStartError(
        cause instanceof Error ? cause.message : "Run could not start.",
      );
    } finally {
      setBusy(false);
      reload();
    }
  }
  return (
    <section className="panel run-panel" aria-labelledby="run-title">
      <div className="section-title">
        <div>
          <span className="eyebrow">The agent's plan</span>
          <h2 id="run-title">Queue run</h2>
        </div>
        <span className="muted">{eligible} eligible claims</span>
      </div>
      <RunControls disabled={disabled} start={start} />
      <p className="muted">
        A cap counts distinct claims, including failures. Retries use the same
        slot. Starting a run makes paid model calls.
      </p>
      {(startError ?? error) && (
        <p className="error" role="alert">
          {startError ?? error} <button onClick={reload}>Refresh run</button>
        </p>
      )}
      {!runs && !error && <p role="status">Loading run…</p>}
      {runs?.length === 0 && <p className="muted">No agent runs yet.</p>}
      {latest && <RunProgress run={latest} select={select} />}
    </section>
  );
}

function RunControls({
  disabled,
  start,
}: {
  readonly disabled: boolean;
  readonly start: (cap: number | null) => Promise<void>;
}) {
  const [cap, setCap] = useState("5");
  const valid = Number.isSafeInteger(Number(cap)) && Number(cap) > 0;
  return (
    <div className="run-controls">
      <button
        className="primary"
        disabled={disabled}
        onClick={() => void start(null)}
      >
        Start queue
      </button>
      <label htmlFor="claim-cap">Claim cap</label>
      <input
        id="claim-cap"
        type="number"
        min="1"
        step="1"
        value={cap}
        aria-invalid={!valid}
        onChange={(event) => {
          setCap(event.target.value);
        }}
      />
      <button
        className="primary"
        disabled={disabled || !valid}
        onClick={() => void start(Number(cap))}
      >
        Start capped run
      </button>
    </div>
  );
}

function RunProgress({
  run: latest,
  select,
}: {
  readonly run: AgentRun;
  readonly select: (claimId: string) => void;
}) {
  const active = latest.status === "running";
  return (
    <div aria-live="polite">
      <p className="run-heading">
        <strong>
          {active ? "Agent working the queue" : `Run ${latest.status}`}
        </strong>
        <span className="mono">{latest.run_id}</span>
      </p>
      {latest.summary && <p>{latest.summary}</p>}
      {latest.error && (
        <p className="error" role="alert">
          {latest.error}
        </p>
      )}
      <ol className="todo-list" aria-label="Run to-do list">
        {latest.tasks.map((task) => (
          <li key={task.task_id} data-task-state={task.state}>
            <button
              className="todo-link mono"
              onClick={() => {
                select(task.claim_id);
              }}
            >
              Review {task.claim_id}
            </button>
            <span className={`task-state ${task.state}`}>
              {taskLabels[task.state]}
            </span>
            {task.reason && <span className="muted">{task.reason}</span>}
          </li>
        ))}
      </ol>
      {active && latest.tasks.length === 0 && (
        <p className="muted">The agent is preparing its to-do list.</p>
      )}
    </div>
  );
}
