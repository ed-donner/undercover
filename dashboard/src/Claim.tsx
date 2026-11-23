import { useCallback, useState } from "react";
import {
  getClaim,
  getRunStatus,
  listHandlers,
  listSteps,
  signOffClaim,
  startClaimRun,
} from "./api";
import type { ClaimDetail, Handler, RunStatus, Step } from "./api";
import { decisionLabel, errorText, money, sentence, stepLabel } from "./format";
import { useData } from "./hooks";
import { StateBadge } from "./StateBadge";

interface ClaimData {
  detail: ClaimDetail;
  steps: Step[];
  handlers: Handler[];
  run: RunStatus;
}

const keepFresh = ({ detail, run }: ClaimData) =>
  run.active || detail.state === "in progress";

function DecisionPanel({ detail }: Readonly<{ detail: ClaimDetail }>) {
  const { decision } = detail;
  return (
    <section className="panel">
      <h2>Decision</h2>
      {decision ? (
        <>
          <p>
            <strong>{decisionLabel[decision.decision]}</strong>
            {decision.decision === "approve" && (
              <>
                {" "}
                with a payout of{" "}
                <span className="mono">{money(decision.payout)}</span>
              </>
            )}
          </p>
          <p>{decision.explanation}</p>
          <p className="muted">
            Policy section:{" "}
            <span className="mono">{decision.policy_section}</span>
          </p>
        </>
      ) : (
        <p className="muted">No decision yet.</p>
      )}
    </section>
  );
}

function SignOff({
  claimId,
  handlers,
  onDone,
}: Readonly<{
  claimId: string;
  handlers: Handler[];
  onDone: () => void;
}>) {
  const allowed = handlers.filter((handler) => handler.can_approve_over_limit);
  const [handlerId, setHandlerId] = useState(allowed.at(0)?.handler_id ?? "");
  const [problem, setProblem] = useState<string>();

  const signOff = () => {
    signOffClaim(claimId, handlerId)
      .then(onDone)
      .catch((cause: unknown) => {
        setProblem(errorText(cause));
      });
  };

  return (
    <>
      <p className="alert">
        This payout is over the approval limit. The payment is blocked until a
        handler signs it off.
      </p>
      <div className="row">
        <label>
          Signing off as{" "}
          <select
            value={handlerId}
            onChange={(event) => {
              setHandlerId(event.target.value);
            }}
          >
            {allowed.map((handler) => (
              <option key={handler.handler_id} value={handler.handler_id}>
                {handler.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={signOff}>
          Sign off and pay
        </button>
      </div>
      {problem && <p className="alert">{problem}</p>}
    </>
  );
}

function PaymentPanel({
  detail,
  handlers,
  onDone,
}: Readonly<{
  detail: ClaimDetail;
  handlers: Handler[];
  onDone: () => void;
}>) {
  const { payment, state, decision } = detail;
  const signedOffBy = handlers.find(
    (handler) => handler.handler_id === payment?.signed_off_by,
  );
  let body = <p className="muted">No payment.</p>;
  if (payment) {
    body = (
      <p>
        Paid <span className="mono">{money(payment.amount)}</span>
        {payment.signed_off_by &&
          `, signed off by ${signedOffBy?.name ?? payment.signed_off_by}`}
        .
      </p>
    );
  } else if (state === "waiting for sign-off") {
    body = (
      <SignOff
        claimId={detail.claim.claim_id}
        handlers={handlers}
        onDone={onDone}
      />
    );
  } else if (decision?.decision === "approve") {
    body = <p className="muted">Approved, not paid yet.</p>;
  }
  return (
    <section className="panel">
      <h2>Payment</h2>
      {body}
    </section>
  );
}

function StepsPanel({ steps }: Readonly<{ steps: Step[] }>) {
  return (
    <section className="panel">
      <h2>What the agent did</h2>
      {steps.length === 0 ? (
        <p className="muted">The agent has not worked on this claim.</p>
      ) : (
        <ol className="steps">
          {steps.map((step) => (
            <li key={step.id}>
              <span className={`kind ${step.kind}`}>
                {stepLabel[step.kind]}
              </span>
              <span className={step.kind === "message" ? "" : "mono"}>
                {step.text}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function ClaimPanel({ detail }: Readonly<{ detail: ClaimDetail }>) {
  const { claim } = detail;
  return (
    <section className="panel">
      <h2>The claim</h2>
      <p className="muted">
        {sentence(claim.claim_type)}, incident on {claim.incident_date} in{" "}
        {claim.incident_location}, filed {claim.submitted_on}
      </p>
      <p className="story">{claim.story}</p>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th className="amount">Amount</th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{sentence(item.category)}</td>
              <td className="amount mono">{money(item.amount)}</td>
            </tr>
          ))}
          <tr>
            <td>
              <strong>Total claimed</strong>
            </td>
            <td />
            <td className="amount mono">
              <strong>{money(claim.amount_claimed)}</strong>
            </td>
          </tr>
        </tbody>
      </table>
      <h3>Documents</h3>
      {claim.documents.map((document) => (
        <div key={document.name} className="document">
          <strong>{document.name}</strong>{" "}
          <span className="muted">{sentence(document.type)}</span>
          <p>{document.content}</p>
        </div>
      ))}
    </section>
  );
}

function BackgroundPanel({ detail }: Readonly<{ detail: ClaimDetail }>) {
  const { policy, plan, customer } = detail;
  return (
    <section className="panel">
      <h2>Policy and customer</h2>
      <p>
        <span className="mono">{policy.policy_id}</span>, {plan.name},
        deductible {money(plan.deductible)}
        {policy.add_ons.length > 0 &&
          `, with ${policy.add_ons.map(sentence).join(", ").toLowerCase()}`}
      </p>
      <p className="muted">
        Trip to {policy.trip.destination}, {policy.trip.departs_on} to{" "}
        {policy.trip.returns_on}, costing {money(policy.trip.trip_cost)}. Bought{" "}
        {policy.purchased_on}. Travelers: {policy.travelers.join(", ")}.
      </p>
      <h3>{customer.name}</h3>
      <p className="muted">Customer since {customer.customer_since}</p>
      {customer.previous_claims.length === 0 ? (
        <p>No earlier claims.</p>
      ) : (
        <ul>
          {customer.previous_claims.map((previous) => (
            <li key={previous.claim_id}>
              <span className="mono">{previous.claim_id}</span>,{" "}
              {previous.filed_on}: {previous.summary}, {previous.outcome}
              {previous.amount_paid > 0 && ` (${money(previous.amount_paid)})`}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Claim({ claimId }: Readonly<{ claimId: string }>) {
  const load = useCallback(async (): Promise<ClaimData> => {
    const [detail, steps, handlers, run] = await Promise.all([
      getClaim(claimId),
      listSteps(claimId),
      listHandlers(),
      getRunStatus(),
    ]);
    return { detail, steps, handlers, run };
  }, [claimId]);
  const { data, error, reload } = useData(load, keepFresh);
  const [problem, setProblem] = useState<string>();

  if (!data) return <p>{error ?? "Loading the claim"}</p>;
  const { detail, steps, handlers, run } = data;

  const start = () => {
    startClaimRun(claimId)
      .then(reload)
      .catch((cause: unknown) => {
        setProblem(errorText(cause));
      });
  };

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <div className="heading">
        <h1>
          <span className="mono">{claimId}</span> {detail.claim.summary}
        </h1>
        <StateBadge state={detail.state} />
      </div>
      <div className="row">
        <button
          type="button"
          onClick={start}
          disabled={run.active || detail.decision !== null}
        >
          Run the agent
        </button>
        {problem && <span className="alert">{problem}</span>}
      </div>
      <DecisionPanel detail={detail} />
      <PaymentPanel detail={detail} handlers={handlers} onDone={reload} />
      <StepsPanel steps={steps} />
      <ClaimPanel detail={detail} />
      <BackgroundPanel detail={detail} />
    </>
  );
}
