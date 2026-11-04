import { useCallback } from "react";
import { listSteps, type Step } from "./api";
import { formatClock } from "./format";
import { POLL_MS, useApi } from "./hooks";

const TOOL_LABELS = new Map([
  ["get_claim", "Reading the claim"],
  ["get_policy", "Reading the policy"],
  ["get_customer", "Reading the claim history"],
  ["get_policy_wording", "Reading the policy wording"],
  ["record_decision", "Recording the decision"],
  ["pay_claim", "Paying the claim"],
]);

export function Steps({ claimId }: Readonly<{ claimId: string }>) {
  const load = useCallback(() => listSteps(claimId), [claimId]);
  const { data: steps } = useApi(load, POLL_MS);
  return (
    <section className="panel" aria-label="The agent's steps">
      <h2>The agent&apos;s steps</h2>
      {steps?.length === 0 && <p className="muted">No steps yet.</p>}
      <ol className="steps">
        {steps?.map((step) => (
          <li key={step.step_id} className="step">
            <span className="mono muted small">
              {formatClock(step.created_at)}
            </span>
            <StepBody step={step} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function StepBody({ step }: Readonly<{ step: Step }>) {
  if (step.kind === "reply")
    return <p className="step-reply">{step.content}</p>;
  if (step.kind === "tool_call") {
    return (
      <div>
        <strong>{TOOL_LABELS.get(step.name) ?? step.name}</strong>
        <code className="block mono small">{step.content}</code>
      </div>
    );
  }
  const refused = refusal(step.content);
  return (
    <div>
      {refused && (
        <p className="refusal">
          <span className="badge refused">Refused</span> {refused}
        </p>
      )}
      <details>
        <summary>What {step.name} returned</summary>
        <pre>{step.content}</pre>
      </details>
    </div>
  );
}

/** The claims system's reason for refusing a request, if it refused. */
function refusal(content: string): string | undefined {
  if (!content.startsWith('{"detail":')) return undefined;
  const { detail } = JSON.parse(content) as { detail: unknown };
  return typeof detail === "string" ? detail : "The request wasn't valid.";
}
