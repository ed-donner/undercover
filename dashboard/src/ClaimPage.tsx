import { useCallback, useState } from "react";
import {
  api,
  type ClaimDetail,
  type Handler,
  type Policy,
  type Step,
} from "./api";
import { Badge } from "./Badge";
import { DECISION_LABELS, money, words } from "./format";
import { useAction, useLoad } from "./hooks";

const STEP_LABELS: Record<Step["kind"], string> = {
  tool_call: "Called",
  tool_result: "Result",
  reply: "Reply",
  error: "Error",
};

function ClaimFacts({ claim }: Readonly<{ claim: ClaimDetail }>) {
  return (
    <section className="panel">
      <h2>The claim</h2>
      <dl className="facts">
        <dt>Type</dt>
        <dd>{words(claim.claim_type)}</dd>
        <dt>Incident</dt>
        <dd>
          <span className="mono">{claim.incident_date}</span>,{" "}
          {claim.incident_location}
        </dd>
        <dt>Submitted</dt>
        <dd className="mono">{claim.submitted_on}</dd>
        <dt>Claimed</dt>
        <dd className="mono">{money(claim.amount_claimed)}</dd>
      </dl>
      <p className="story">{claim.story}</p>
    </section>
  );
}

function Items({ claim }: Readonly<{ claim: ClaimDetail }>) {
  return (
    <section className="panel">
      <h2>Items claimed</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col">Category</th>
            <th scope="col" className="number">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{words(item.category)}</td>
              <td className="number mono">{money(item.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Documents({ claim }: Readonly<{ claim: ClaimDetail }>) {
  return (
    <section className="panel">
      <h2>Documents</h2>
      <div className="documents">
        {claim.documents.map((document) => (
          <article key={document.name} className="document">
            <h3>{document.name}</h3>
            <p className="note">{words(document.type)}</p>
            <p>{document.content}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function PolicyFacts({ policy }: Readonly<{ policy: Policy }>) {
  const addOns = policy.add_on_details.map((addOn) => addOn.name).join(", ");
  return (
    <section className="panel">
      <h2>
        Policy <span className="mono">{policy.policy_id}</span>
      </h2>
      <dl className="facts">
        <dt>Plan</dt>
        <dd>{policy.plan_details.name}</dd>
        <dt>Add-ons</dt>
        <dd>{addOns || "None"}</dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination},{" "}
          <span className="mono">
            {policy.trip.departs_on} to {policy.trip.returns_on}
          </span>
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Bought</dt>
        <dd className="mono">{policy.purchased_on}</dd>
      </dl>
    </section>
  );
}

function SignOffForm({
  claimId,
  handlers,
  onSignedOff,
}: Readonly<{
  claimId: string;
  handlers: Handler[];
  onSignedOff: () => void;
}>) {
  const [handlerId, setHandlerId] = useState("");
  const action = useAction();
  const eligible = handlers.filter((handler) => handler.can_approve_over_limit);

  return (
    <form
      className="sign-off"
      onSubmit={(event) => {
        event.preventDefault();
        void action.act(async () => {
          await api.signOff(claimId, handlerId);
          onSignedOff();
        });
      }}
    >
      <label htmlFor="handler">Handler</label>
      <select
        id="handler"
        value={handlerId}
        onChange={(event) => {
          setHandlerId(event.target.value);
        }}
      >
        <option value="">Choose a handler</option>
        {eligible.map((handler) => (
          <option key={handler.handler_id} value={handler.handler_id}>
            {handler.name}
          </option>
        ))}
      </select>
      <button type="submit" disabled={!handlerId || action.busy}>
        Sign off and pay
      </button>
      {action.error && <p role="alert">{action.error}</p>}
    </form>
  );
}

function Payment({
  claim,
  handlers,
}: Readonly<{ claim: ClaimDetail; handlers: Handler[] }>) {
  if (claim.payment) {
    const handler = handlers.find(
      (h) => h.handler_id === claim.sign_off?.handler_id,
    );
    return (
      <p className="payment">
        Paid <span className="mono">{money(claim.payment.amount)}</span>
        {handler && ` after sign-off by ${handler.name}`}
      </p>
    );
  }
  if (claim.status === "awaiting_sign_off") {
    return (
      <p className="payment">
        The payment waits for a handler&apos;s sign-off.
      </p>
    );
  }
  return claim.decision?.decision === "approve" ? (
    <p className="payment">Not paid yet.</p>
  ) : null;
}

function DecisionPanel({
  claim,
  handlers,
  onChange,
}: Readonly<{
  claim: ClaimDetail;
  handlers: Handler[];
  onChange: () => void;
}>) {
  const { decision } = claim;
  if (!decision) {
    return (
      <section className="panel">
        <h2>Decision</h2>
        <p className="note">
          {claim.status === "in_progress"
            ? "The agent is working on this claim."
            : "No decision yet."}
        </p>
      </section>
    );
  }
  return (
    <section className="panel">
      <h2>Decision</h2>
      <p className="decision">
        <span className={`chip chip-${decision.decision}`}>
          {DECISION_LABELS[decision.decision]}
        </span>
        <span className="mono payout">{money(decision.payout)}</span>
      </p>
      <p>{decision.reason}</p>
      <p className="note">Policy wording: {decision.policy_section}</p>
      <Payment claim={claim} handlers={handlers} />
      {claim.status === "awaiting_sign_off" && (
        <SignOffForm
          claimId={claim.claim_id}
          handlers={handlers}
          onSignedOff={onChange}
        />
      )}
    </section>
  );
}

function Steps({
  steps,
  working,
}: Readonly<{ steps: Step[]; working: boolean }>) {
  const idle = working
    ? "The agent is starting."
    : "The agent has not worked on this claim yet.";
  return (
    <section className="panel">
      <h2>The agent at work</h2>
      {steps.length === 0 ? (
        <p className="note">{idle}</p>
      ) : (
        <ol className="steps" aria-label="Agent steps">
          {steps.map((step) => (
            <li key={step.id} className={`step step-${step.kind}`}>
              <span className="step-kind">{STEP_LABELS[step.kind]}</span>
              <span className={step.kind === "reply" ? "" : "mono"}>
                {step.text}
              </span>
            </li>
          ))}
        </ol>
      )}
      {working && steps.length > 0 && <p className="note">Working...</p>}
    </section>
  );
}

// The agent keeps working after it decides, to pay, until its reply or an error.
function working(claim: ClaimDetail, steps: Step[]): boolean {
  const last = steps.at(-1);
  if (claim.status === "in_progress") return true;
  return last !== undefined && last.kind !== "reply" && last.kind !== "error";
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const load = useCallback(async () => {
    const claim = await api.claim(claimId);
    const [policy, steps] = await Promise.all([
      api.policy(claim.policy_id),
      api.steps(claimId),
    ]);
    return { claim, policy, steps };
  }, [claimId]);
  const { data, error, refresh } = useLoad(load, (loaded) =>
    Boolean(loaded && working(loaded.claim, loaded.steps)),
  );
  const { data: handlers } = useLoad(api.handlers);
  const run = useAction();

  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading the claim...</p>;

  const { claim, policy, steps } = data;
  const runAgent = () =>
    run.act(async () => {
      await api.runAgent(claimId);
      refresh();
    });

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <div className="page-head">
        <h1>
          <span className="mono">{claim.claim_id}</span> {claim.summary}
        </h1>
        <div className="actions">
          <Badge status={claim.status} />
          {claim.status === "waiting" && (
            <button
              type="button"
              onClick={() => void runAgent()}
              disabled={run.busy}
            >
              Run agent
            </button>
          )}
        </div>
      </div>
      {run.error && <p role="alert">{run.error}</p>}
      <div className="claim-grid">
        <div className="column">
          <ClaimFacts claim={claim} />
          <Items claim={claim} />
          <Documents claim={claim} />
        </div>
        <div className="column">
          <DecisionPanel
            claim={claim}
            handlers={handlers ?? []}
            onChange={refresh}
          />
          <Steps steps={steps} working={working(claim, steps)} />
          <PolicyFacts policy={policy} />
        </div>
      </div>
    </>
  );
}
