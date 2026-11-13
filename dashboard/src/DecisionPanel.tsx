import { useState } from "react";
import { post } from "./api";
import { money, statuses } from "./display";
import type { ActivityEvent, Claim, Handler, Run } from "./types";

export function DecisionPanel({ claim }: { readonly claim: Claim }) {
  const decision = claim.decision;
  return (
    <section className="panel decision-panel" aria-labelledby="decision-title">
      <div className="section-title">
        <h3 id="decision-title">Agent decision</h3>
        <span className="eyebrow">Policy-led review</span>
      </div>
      {decision ? (
        <>
          <div className="decision-heading">
            <span className={`outcome ${decision.outcome}`}>
              {decision.outcome}
            </span>
            <strong className="payout">{money(decision.payout)}</strong>
          </div>
          <p className="story">{decision.explanation}</p>
          <h4>Payout calculation</h4>
          <p className="document-text">{decision.calculation}</p>
          <p className="muted">
            Policy sections {decision.policy_sections.join(", ")} · Recorded{" "}
            {decision.recorded_at}
          </p>
          <p className="muted">
            {decision.manual_version
              ? `Claims manual ${decision.manual_version}, sections ${decision.manual_sections.join(", ")}`
              : "Historical decision: manual provenance not recorded."}
          </p>
          {claim.sign_off && (
            <p>
              Signed off by{" "}
              <span className="mono">{claim.sign_off.handler_id}</span> ·{" "}
              {claim.sign_off.signed_at}
            </p>
          )}
          <p className={claim.payment ? "payment paid" : "payment"}>
            {claim.payment
              ? `Simulated payment recorded: ${money(claim.payment.amount)}`
              : "No simulated payment recorded."}
          </p>
          {claim.payment && (
            <small className="muted">{claim.payment.paid_at}</small>
          )}
        </>
      ) : (
        <div className="empty-state">
          <span className="empty-symbol" aria-hidden="true">
            ◎
          </span>
          <p>No decision yet.</p>
          <small>
            The agent will check the evidence against the wording and claims
            manual.
          </small>
        </div>
      )}
    </section>
  );
}

async function performAction(claimId: string, suffix: string, body: object) {
  return post(
    suffix === "runs" ? "/agent-runs" : `/claims/${claimId}/${suffix}`,
    suffix === "runs" ? { mode: "claim", claim_id: claimId } : body,
  );
}

function needsPayment(claim: Claim) {
  return (
    claim.status === "decided" &&
    claim.decision?.outcome === "approve" &&
    !claim.payment
  );
}

export function ClaimActions({
  claim,
  handlers,
  runs,
  onChange,
  runActive = false,
}: {
  readonly claim: Claim;
  readonly handlers: Handler[];
  readonly runs: Run[];
  readonly onChange: () => void;
  readonly runActive?: boolean;
}) {
  const [handler, setHandler] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const failed = runs.at(-1)?.status === "failed";
  async function act(suffix: string, body: object = {}) {
    setBusy(true);
    setError(undefined);
    try {
      await performAction(claim.claim_id, suffix, body);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Action failed.");
    } finally {
      setBusy(false);
      onChange();
    }
  }
  return (
    <section className="panel action-panel" aria-label="Claim actions">
      <div>
        <span className={`status ${claim.status}`}>
          {statuses[claim.status]}
        </span>
        <p className="muted">
          {claim.status === "waiting_for_sign_off"
            ? "Payment is blocked until a handler signs off."
            : "All payments in this pilot are simulated."}
        </p>
      </div>
      {claim.needs_handler && (
        <p className="handler-label">
          Left for a handler: {claim.handler_reason}
        </p>
      )}
      {claim.status === "waiting" && !claim.needs_handler && (
        <button
          className="primary"
          disabled={busy || runActive}
          onClick={() => void act("runs")}
        >
          {failed ? "Retry claim" : "Process claim"}
          <span aria-hidden="true"> ↗</span>
        </button>
      )}
      {claim.status === "in_progress" && (
        <p role="status" className="working">
          Agent working
          <span className="pulse" />
        </p>
      )}
      {claim.status === "waiting_for_sign_off" && (
        <div className="sign-off-controls">
          <label htmlFor="handler">Signing handler</label>
          <select
            id="handler"
            value={handler}
            onChange={(event) => {
              setHandler(event.target.value);
            }}
          >
            <option value="">Choose a handler</option>
            {handlers
              .filter((item) => item.can_approve_over_limit)
              .map((item) => (
                <option key={item.handler_id} value={item.handler_id}>
                  {item.name}
                </option>
              ))}
          </select>
          <button
            className="primary"
            disabled={busy || !handler}
            onClick={() => void act("sign-off", { handler_id: handler })}
          >
            Sign off payout
          </button>
        </div>
      )}
      {needsPayment(claim) && (
        <button
          className="primary"
          disabled={busy}
          onClick={() =>
            void act("payment", { amount: claim.decision?.payout })
          }
        >
          Record simulated payment
        </button>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}

export function ActivityPanel({
  events,
  runs,
}: {
  readonly events: ActivityEvent[];
  readonly runs: Run[];
}) {
  const latest = runs.at(-1);
  return (
    <section className="panel activity-panel" aria-labelledby="activity-title">
      <div className="section-title">
        <h3 id="activity-title">Agent activity</h3>
        <span className="live-label">
          <span className="pulse" /> Live updates
        </span>
      </div>
      <p className="muted">Observable steps, not private model reasoning.</p>
      {latest?.error && (
        <p role="alert" className="error">
          {latest.error}
        </p>
      )}
      <ol
        className="activity-list"
        aria-live="polite"
        aria-relevant="additions"
      >
        {events.map((event) => (
          <li
            key={event.sequence}
            className={event.kind === "run_failed" ? "failed-event" : ""}
          >
            <span className="activity-dot" aria-hidden="true" />
            <div>
              <strong>{event.label}</strong>
              <time dateTime={event.created_at}>{event.created_at}</time>
            </div>
          </li>
        ))}
      </ol>
      {events.length === 0 && (
        <p className="muted">No activity yet. Process this claim to begin.</p>
      )}
      {latest && (
        <details className="document">
          <summary>Run details</summary>
          <p className="mono">Run {latest.run_id}</p>
          <p className="mono">Thread {latest.thread_id}</p>
          <p>
            {latest.status} · {latest.started_at}
          </p>
        </details>
      )}
    </section>
  );
}
