import { timeText } from "./format";
import type { Step } from "./types";

const KIND_LABELS: Record<Step["kind"], string> = {
  tool_call: "Tool call",
  tool_result: "Result",
  message: "Message",
  error: "Error",
};

export function Steps({ steps }: Readonly<{ steps: Step[] }>) {
  if (steps.length === 0) return <p className="muted">No steps yet.</p>;
  return (
    <ol className="steps">
      {steps.map((step) => (
        <li key={step.id} className={`step step-${step.kind}`}>
          <span className="step-time mono">{timeText(step.created_at)}</span>
          <span className="step-kind">{KIND_LABELS[step.kind]}</span>
          <span className={step.kind === "message" ? "" : "mono step-text"}>
            {step.text}
          </span>
        </li>
      ))}
    </ol>
  );
}
