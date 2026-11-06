import { useCallback } from "react";
import {
  type Claim,
  getClaim,
  getCustomer,
  getPolicy,
  type Handler,
  listHandlers,
} from "./api";
import { DecisionLabel, StatusBadge, Unreachable } from "./common";
import { formatDate, formatMoment, humanize, money } from "./format";
import { POLL_MS, useApi } from "./hooks";
import { SignOff } from "./SignOff";
import { Steps } from "./Steps";

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const loadClaim = useCallback(() => getClaim(claimId), [claimId]);
  const { data: claim, failed, reload } = useApi(loadClaim, POLL_MS);
  const { data: handlers } = useApi(listHandlers);
  if (!claim) {
    return (
      <>
        <BackToQueue />
        {failed ? (
          <p role="alert" className="alert">
            Can&apos;t load claim {claimId}. It may not exist, or the claims
            system may be down.
          </p>
        ) : (
          <p className="muted">Loading claim {claimId}.</p>
        )}
      </>
    );
  }
  return (
    <>
      <BackToQueue />
      <div className="claim-title">
        <h1>{claim.summary}</h1>
        <span className="mono muted">{claim.claim_id}</span>
        <StatusBadge status={claim.status} />
      </div>
      {failed && <Unreachable />}
      <Outcome claim={claim} handlers={handlers ?? []} onSignedOff={reload} />
      <div className="columns">
        <ClaimDetails claim={claim} />
        <Steps claimId={claim.claim_id} />
      </div>
      <div className="columns">
        <PolicyDetails policyId={claim.policy_id} />
        <CustomerDetails customerId={claim.customer_id} />
      </div>
    </>
  );
}

function BackToQueue() {
  return (
    <p className="back">
      <a href="#/">Back to the queue</a>
    </p>
  );
}

function Outcome({
  claim,
  handlers,
  onSignedOff,
}: Readonly<{ claim: Claim; handlers: Handler[]; onSignedOff: () => void }>) {
  if (!claim.decision) {
    return (
      <section className="panel" aria-label="Decision">
        <h2>Decision</h2>
        <p className="muted">{undecided(claim)}</p>
      </section>
    );
  }
  return (
    <section className="panel outcome" aria-label="Decision">
      <div className="outcome-head">
        <DecisionLabel decision={claim.decision} />
        {claim.decision === "approve" && (
          <span className="payout">{money(claim.payout ?? 0)}</span>
        )}
      </div>
      <blockquote className="reason">{claim.reason}</blockquote>
      <p className="muted">Relied on: {claim.policy_section}</p>
      <Payment claim={claim} handlers={handlers} onSignedOff={onSignedOff} />
    </section>
  );
}

function Payment({
  claim,
  handlers,
  onSignedOff,
}: Readonly<{ claim: Claim; handlers: Handler[]; onSignedOff: () => void }>) {
  if (claim.decision === "decline") return <p>Nothing to pay.</p>;
  if (claim.decision === "refer") {
    return <p>A handler takes this claim from here.</p>;
  }
  if (claim.status === "left_for_handler") {
    return (
      <p>
        The agent approved this claim but couldn&apos;t pay it, so it&apos;s
        left for a handler.
      </p>
    );
  }
  if (claim.status === "waiting_for_sign_off") {
    return (
      <>
        <p>
          This payout waits for a handler&apos;s sign-off before it is paid.
        </p>
        <SignOff claim={claim} handlers={handlers} onSignedOff={onSignedOff} />
      </>
    );
  }
  if (claim.paid_amount === null || claim.paid_at === null) {
    return <p>Not paid yet.</p>;
  }
  const signer = handlers.find(
    (handler) => handler.handler_id === claim.signed_off_by,
  );
  return (
    <p>
      Paid {money(claim.paid_amount)} on {formatMoment(claim.paid_at)}.
      {claim.signed_off_by && (
        <> Signed off by {signer?.name ?? claim.signed_off_by}.</>
      )}
    </p>
  );
}

function undecided(claim: Claim): string {
  if (claim.status === "left_for_handler") {
    return "The agent couldn't finish this claim in two attempts, so it's left for a handler. Its steps show what went wrong.";
  }
  if (claim.status === "in_progress")
    return "The agent is working on this claim.";
  if (claim.attempts > 0) {
    return "The agent's last attempt at this claim failed, so it's back in the queue for one more try.";
  }
  return "The agent hasn't started on this claim.";
}

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel" aria-label="Claim">
      <h2>The claim</h2>
      <dl className="facts">
        <dt>Type</dt>
        <dd>{humanize(claim.claim_type)}</dd>
        <dt>What happened</dt>
        <dd>
          {formatDate(claim.incident_date)}, {claim.incident_location}
        </dd>
        <dt>Submitted</dt>
        <dd>{formatDate(claim.submitted_on)}</dd>
      </dl>
      <h3>The customer&apos;s story</h3>
      <p className="story">{claim.story}</p>
      <h3>Items claimed</h3>
      <table className="items">
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td className="muted">{humanize(item.category)}</td>
              <td className="number">{money(item.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" colSpan={2}>
              Total
            </th>
            <td className="number">{money(claim.amount_claimed)}</td>
          </tr>
        </tfoot>
      </table>
      <h3>Documents</h3>
      {claim.documents.map((document) => (
        <article className="document" key={document.name}>
          <h4>
            {document.name}{" "}
            <span className="muted small">{humanize(document.type)}</span>
          </h4>
          <p>{document.content}</p>
        </article>
      ))}
    </section>
  );
}

function PolicyDetails({ policyId }: Readonly<{ policyId: string }>) {
  const load = useCallback(() => getPolicy(policyId), [policyId]);
  const { data: policy } = useApi(load);
  return (
    <section className="panel" aria-label="Policy">
      <h2>
        Policy <span className="mono muted small">{policyId}</span>
      </h2>
      {policy && (
        <dl className="facts">
          <dt>Plan</dt>
          <dd>{policy.plan_details.name}</dd>
          <dt>Add-ons</dt>
          <dd>
            {policy.add_on_details.map((addOn) => addOn.name).join(", ") ||
              "None"}
          </dd>
          <dt>Deductible</dt>
          <dd>{money(policy.plan_details.deductible)}</dd>
          <dt>Trip</dt>
          <dd>
            {policy.trip.destination}, {formatDate(policy.trip.departs_on)} to{" "}
            {formatDate(policy.trip.returns_on)}
          </dd>
          <dt>Trip cost</dt>
          <dd>{money(policy.trip.trip_cost)}</dd>
          <dt>Travelers</dt>
          <dd>{policy.travelers.join(", ")}</dd>
          <dt>Bought</dt>
          <dd>
            {formatDate(policy.purchased_on)} through {policy.sold_through}
          </dd>
        </dl>
      )}
    </section>
  );
}

function CustomerDetails({ customerId }: Readonly<{ customerId: string }>) {
  const load = useCallback(() => getCustomer(customerId), [customerId]);
  const { data: customer } = useApi(load);
  return (
    <section className="panel" aria-label="Customer">
      <h2>Customer</h2>
      {customer && (
        <>
          <dl className="facts">
            <dt>Name</dt>
            <dd>{customer.name}</dd>
            <dt>Customer since</dt>
            <dd>{formatDate(customer.customer_since)}</dd>
            <dt>Email</dt>
            <dd>{customer.email}</dd>
            <dt>Phone</dt>
            <dd>{customer.phone}</dd>
          </dl>
          <h3>Earlier claims</h3>
          {customer.previous_claims.length === 0 && (
            <p className="muted">None.</p>
          )}
          {customer.previous_claims.map((earlier) => (
            <article className="document" key={earlier.claim_id}>
              <h4>
                <span className="mono">{earlier.claim_id}</span>{" "}
                <span className="muted small">
                  {humanize(earlier.claim_type)}, filed{" "}
                  {formatDate(earlier.filed_on)}
                </span>
              </h4>
              <p>
                {earlier.summary}. {humanize(earlier.outcome)}, paid{" "}
                {money(earlier.amount_paid)}.
              </p>
            </article>
          ))}
        </>
      )}
    </section>
  );
}
