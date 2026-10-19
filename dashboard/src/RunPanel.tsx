import { RUN_LABELS, TODO_LABELS } from "./format";
import type { Run } from "./types";

export function RunPanel({ run }: Readonly<{ run: Run }>) {
  const title = run.status === "running" ? "Current run" : "Last run";
  return (
    <section className="panel run">
      <div className="row">
        <h2>{title}</h2>
        <span className={`chip chip-run-${run.status}`}>
          {RUN_LABELS[run.status]}
        </span>
        <span className="muted">
          Up to <span className="mono">{run.limit}</span>{" "}
          {run.limit === 1 ? "claim" : "claims"}
        </span>
      </div>
      {run.todos.length === 0 ? (
        <p className="muted">
          {run.status === "running"
            ? "The agent is planning its work."
            : "The agent made no plan."}
        </p>
      ) : (
        <ul className="todos">
          {run.todos.map((todo, index) => (
            <li key={`${String(index)} ${todo.text}`}>
              <span className={`chip chip-todo-${todo.status}`}>
                {TODO_LABELS[todo.status]}
              </span>
              <span>{todo.text}</span>
            </li>
          ))}
        </ul>
      )}
      {run.summary && <p className="quote">{run.summary}</p>}
    </section>
  );
}
