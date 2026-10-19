import { useCallback, useState } from "react";
import { runClaim } from "./api";
import { Background } from "./Background";
import { loadClaimPage, settled } from "./claimPage";
import { claimType, dateText, money, OUTCOME_LABELS } from "./format";
import { SignOffPanel } from "./SignOffPanel";
import { StatusChip } from "./StatusChip";
import { Reads, Steps } from "./Steps";
import type { ClaimDetail } from "./types";
import { usePolled } from "./usePolled";

const REFRESH_MS = 2000;

function Outcome({ claim }: Readonly<{ claim: ClaimDetail }>) {
  const { decision, payment, sign_off: signOff } = claim;
  if (!decision) return null;
  let paymentText = "No payment has been made.";
  if (payment)
    paymentText = `Paid ${money(payment.amount)} on ${dateText(payment.paid_at.slice(0, 10))}.`;
  else if (claim.status === "waiting_for_sign_off")
    paymentText = "The payment is held until a handler signs off.";
  else if (decision.decision !== "approve") paymentText = "Nothing to pay.";
  return (
    <section className="panel">
      <h2>
        {OUTCOME_LABELS[decision.decision]}
        {decision.decision === "approve" && `, ${money(decision.payout)}`}
      </h2>
      <p className="quote">{decision.explanation}</p>
      <dl className="facts">
        <dt>Policy section</dt>
        <dd>{decision.policy_section}</dd>
        <dt>Payment</dt>
        <dd>{paymentText}</dd>
        {signOff && (
          <>
            <dt>Signed off by</dt>
            <dd>
              {signOff.handler_name}, {dateText(signOff.signed_at.slice(0, 10))}
            </dd>
          </>
        )}
      </dl>
    </section>
  );
}

export function ClaimView({ id }: Readonly<{ id: string }>) {
  const load = useCallback(() => loadClaimPage(id), [id]);
  const { data, error, reload } = usePolled(load, REFRESH_MS, settled);
  const [failed, setFailed] = useState(false);

  if (!data) {
    return (
      <p role={error ? "alert" : "status"}>
        {error ? "This claim could not be loaded." : "Loading the claim"}
      </p>
    );
  }
  const { claim, steps } = data;

  const run = () => {
    setFailed(false);
    runClaim(claim.claim_id)
      .then(reload)
      .catch(() => {
        setFailed(true);
      });
  };

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <div className="toolbar">
        <h1>
          <span className="mono">{claim.claim_id}</span> {claim.summary}
        </h1>
        <div className="row">
          <StatusChip status={claim.status} />
          {claim.status === "waiting" && (
            <button className="primary" onClick={run}>
              Run agent
            </button>
          )}
        </div>
      </div>
      {failed && (
        <p role="alert" className="alert">
          The agent could not be started.
        </p>
      )}
      <div className="stack">
        {claim.status === "waiting_for_sign_off" && (
          <SignOffPanel claim={claim} onSignedOff={reload} />
        )}
        {claim.status === "needs_handler" && (
          <section className="panel">
            <h2>Needs a handler</h2>
            <p>
              The agent could not finish this claim after two tries. A handler
              needs to work it.
            </p>
          </section>
        )}
        <Outcome claim={claim} />
        <Reads steps={steps} />
        <section className="panel">
          <h2>What the agent did</h2>
          <Steps steps={steps} />
        </section>
        <section className="panel">
          <h2>The claim</h2>
          <dl className="facts">
            <dt>Customer</dt>
            <dd>{claim.customer_name}</dd>
            <dt>Type</dt>
            <dd>{claimType(claim.claim_type)}</dd>
            <dt>Incident</dt>
            <dd>
              {dateText(claim.incident_date)}, {claim.incident_location}
            </dd>
            <dt>Submitted</dt>
            <dd>{dateText(claim.submitted_on)}</dd>
            <dt>Claimed</dt>
            <dd className="mono">{money(claim.amount_claimed)}</dd>
          </dl>
          <p className="quote">{claim.story}</p>
          <h3>Items</h3>
          <ul className="history">
            {claim.items.map((item) => (
              <li key={item.description}>
                {item.description}:{" "}
                <span className="mono">{money(item.amount)}</span>
              </li>
            ))}
          </ul>
          <h3>Documents</h3>
          {claim.documents.map((document) => (
            <details key={document.name}>
              <summary>
                {document.name}{" "}
                <span className="muted">({claimType(document.type)})</span>
              </summary>
              <p>{document.content}</p>
            </details>
          ))}
        </section>
        <Background claim={claim} />
      </div>
    </>
  );
}
