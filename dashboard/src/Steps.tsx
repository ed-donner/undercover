import type { Step } from "./api";

const KINDS: Record<Step["kind"], string> = {
  tool_call: "Action",
  tool_result: "Result",
  message: "Agent",
  error: "Problem",
};

export function Steps({
  steps,
  working,
}: Readonly<{ steps: Step[]; working: boolean }>) {
  return (
    <section className="panel" aria-label="Agent steps">
      <h2>What the agent did</h2>
      {steps.length === 0 && !working && (
        <p className="muted">The agent has not worked on this claim yet.</p>
      )}
      <ol className="steps">
        {steps.map((step, index) => (
          <li key={index} className={`step-${step.kind}`}>
            <span className="step-kind">{KINDS[step.kind]}</span>
            <span
              className={
                step.kind === "message" ? "step-content" : "step-content mono"
              }
            >
              {step.content}
            </span>
          </li>
        ))}
      </ol>
      {working && <p className="muted">The agent is working...</p>}
    </section>
  );
}
