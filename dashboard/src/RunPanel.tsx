import { getLatestRun, type Run, type TodoStatus } from "./api";
import { formatMoment, TODO_LABELS } from "./format";
import { POLL_MS, useApi } from "./hooks";

export function RunPanel() {
  const { data: run } = useApi(getLatestRun, POLL_MS);
  if (run === undefined) return null;
  return (
    <section className="panel" aria-label="The agent's run">
      <h2>The agent&apos;s run</h2>
      {run === null ? (
        <p className="muted">The agent hasn&apos;t run yet.</p>
      ) : (
        <RunDetails run={run} />
      )}
    </section>
  );
}

function RunDetails({ run }: Readonly<{ run: Run }>) {
  const done = run.todos.filter((todo) => todo.status === "done").length;
  return (
    <>
      <p className="run-head">
        <span className="mono">Run {run.run_id}</span>
        {run.finished_at ? (
          <span className="badge todo-done">Finished</span>
        ) : (
          <span className="badge todo-in_progress">Running</span>
        )}
        <span className="muted">
          Started {formatMoment(run.started_at)}
          {run.finished_at && <>, finished {formatMoment(run.finished_at)}</>}
        </span>
      </p>
      <h3>To-do list</h3>
      {run.todos.length === 0 ? (
        <p className="muted">
          {run.finished_at
            ? "The agent kept no to-do list."
            : "The agent is planning its work."}
        </p>
      ) : (
        <>
          <p className="muted small">
            {done} of {run.todos.length} done
          </p>
          <ol className="todos">
            {run.todos.map((todo, index) => (
              <li key={`${String(index)} ${todo.content}`} className="todo">
                <TodoBadge status={todo.status} />
                <span>{todo.content}</span>
              </li>
            ))}
          </ol>
        </>
      )}
      {run.summary && (
        <>
          <h3>Summary</h3>
          <p className="summary">{run.summary}</p>
        </>
      )}
    </>
  );
}

function TodoBadge({ status }: Readonly<{ status: TodoStatus }>) {
  return <span className={`badge todo-${status}`}>{TODO_LABELS[status]}</span>;
}
