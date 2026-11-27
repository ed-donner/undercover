import { useState } from "react";
import {
  type Claim,
  type Step,
  type StepKind,
  endpoints,
  postJson,
  useApi,
} from "./api";
import { ErrorPanel } from "./components";
import { money } from "./format";

const STEP_LABELS: Record<StepKind, string> = {
  tool_call: "Called",
  tool_result: "Result",
  message: "Agent",
  error: "Error",
};

function useAction(onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const act = (path: string, body: unknown) => {
    setBusy(true);
    setError(undefined);
    postJson(path, body).then(
      () => {
        setBusy(false);
        onDone();
      },
      (failure: unknown) => {
        setBusy(false);
        setError(failure instanceof Error ? failure.message : String(failure));
      },
    );
  };
  return { busy, error, act };
}

export function RunPanel({
  claimId,
  onStarted,
}: Readonly<{ claimId: string; onStarted: () => void }>) {
  const { busy, error, act } = useAction(onStarted);
  return (
    <section className="panel">
      <h2>UnderCover Agent</h2>
      <p className="muted">This claim is waiting in the queue.</p>
      <button
        type="button"
        className="button"
        disabled={busy}
        onClick={() => {
          act(`/api/claims/${claimId}/run`, {});
        }}
      >
        Run agent
      </button>
      {error && <ErrorPanel message={error} />}
    </section>
  );
}

function StepItem({ step }: Readonly<{ step: Step }>) {
  const time = step.created_at.slice(11, 19);
  return (
    <li className={`step step-${step.kind}`}>
      <span className="step-label">{STEP_LABELS[step.kind]}</span>
      <span className="step-time mono">{time}</span>
      {step.kind === "tool_result" ? (
        <details>
          <summary className="mono">{step.content.split(":")[0]}</summary>
          <p className="step-content mono">{step.content}</p>
        </details>
      ) : (
        <p className="step-content">{step.content}</p>
      )}
    </li>
  );
}

export function StepsPanel({
  steps,
  working,
}: Readonly<{ steps: Step[]; working: boolean }>) {
  if (!steps.length && !working) return null;
  return (
    <section className="panel">
      <h2>What the agent did</h2>
      {working && (
        <p className="muted" role="status">
          The agent is working on this claim.
        </p>
      )}
      <ol className="steps">
        {steps.map((step) => (
          <StepItem step={step} key={step.step_id} />
        ))}
      </ol>
    </section>
  );
}

export function SignOffPanel({
  claim,
  onSigned,
}: Readonly<{ claim: Claim; onSigned: () => void }>) {
  const { data: handlers } = useApi(endpoints.handlers());
  const [handlerId, setHandlerId] = useState("");
  const { busy, error, act } = useAction(onSigned);
  const signers = (handlers ?? []).filter((h) => h.can_approve_over_limit);

  return (
    <section className="panel sign-off">
      <h2>Sign-off needed</h2>
      <p>
        The agent approved a payout of{" "}
        <strong className="mono">{money(claim.decision?.payout ?? 0)}</strong>.
        Payouts over $1,000.00 need a handler&apos;s sign-off, so the payment is
        blocked until then.
      </p>
      <form
        className="sign-off-form"
        onSubmit={(event) => {
          event.preventDefault();
          act(`/api/claims/${claim.claim_id}/sign-off`, {
            handler_id: handlerId,
          });
        }}
      >
        <label htmlFor="handler">Handler</label>
        <select
          id="handler"
          value={handlerId}
          required
          onChange={(event) => {
            setHandlerId(event.target.value);
          }}
        >
          <option value="">Choose a handler</option>
          {signers.map((handler) => (
            <option value={handler.handler_id} key={handler.handler_id}>
              {handler.name}, {handler.role}
            </option>
          ))}
        </select>
        <button type="submit" className="button" disabled={busy || !handlerId}>
          Sign off and pay
        </button>
      </form>
      {error && <ErrorPanel message={error} />}
    </section>
  );
}
