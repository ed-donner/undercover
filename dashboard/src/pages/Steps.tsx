import type { Step } from "../api";

function time(createdAt: string): string {
  return createdAt.slice(11, 19);
}

export function Steps({ steps }: Readonly<{ steps: Step[] }>) {
  return (
    <section className="panel" aria-label="Agent's steps">
      <h2>Agent's steps</h2>
      {steps.length === 0 ? (
        <p className="note">The agent has not started on this claim.</p>
      ) : (
        <ol className="steps">
          {steps.map((step) => (
            <li key={step.id}>
              <span className="mono note">{time(step.created_at)}</span>{" "}
              {step.text}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
