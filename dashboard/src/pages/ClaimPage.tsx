import { useCallback } from "react";
import type { Claim, Policy } from "../api";
import { api } from "../api";
import { claimType, decisionLabels, money } from "../format";
import { StatusBadge } from "../StatusBadge";
import { useData } from "../useData";

function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  const { decision, payment } = claim;
  if (!decision) {
    return (
      <section className="panel">
        <h2>Decision</h2>
        <p>The agent has not decided this claim yet.</p>
      </section>
    );
  }
  return (
    <section className="panel decision">
      <h2>Decision: {decisionLabels[decision.decision]}</h2>
      {decision.decision === "approve" && (
        <p>
          Payout <span className="mono">{money(decision.payout)}</span>
        </p>
      )}
      <blockquote>{decision.reason}</blockquote>
      <p>
        Policy section: <strong>{decision.policy_section}</strong>
      </p>
      {payment && (
        <p>
          Paid <span className="mono">{money(payment.amount)}</span>
          {payment.signed_off_by && `, signed off by ${payment.signed_off_by}`}
        </p>
      )}
    </section>
  );
}

function PolicyPanel({ policy }: Readonly<{ policy: Policy }>) {
  return (
    <section className="panel">
      <h2>Policy</h2>
      <dl>
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan.name}</dd>
        <dt>Add-ons</dt>
        <dd>{policy.add_ons.map((a) => a.name).join(", ") || "None"}</dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {policy.trip.departs_on} to{" "}
          {policy.trip.returns_on}
        </dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
      </dl>
    </section>
  );
}

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <>
      <section className="panel">
        <h2>The customer's story</h2>
        <p className="story">{claim.story}</p>
        <dl>
          <dt>Incident</dt>
          <dd>
            {claim.incident_date}, {claim.incident_location}
          </dd>
          <dt>Submitted</dt>
          <dd>{claim.submitted_on}</dd>
        </dl>
      </section>
      <section className="panel">
        <h2>Items claimed</h2>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{claimType(item.category)}</td>
                <td className="amount mono">{money(item.amount)}</td>
              </tr>
            ))}
            <tr className="total">
              <td colSpan={2}>Total claimed</td>
              <td className="amount mono">{money(claim.amount_claimed)}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Documents</h2>
        {claim.documents.map((doc) => (
          <article key={doc.name} className="document">
            <h3>{doc.name}</h3>
            <p>{doc.content}</p>
          </article>
        ))}
      </section>
    </>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const loadClaim = useCallback(() => api.claim(claimId), [claimId]);
  const loadPolicy = useCallback(() => api.policy(claimId), [claimId]);
  const { data: claim, error } = useData(loadClaim);
  const { data: policy } = useData(loadPolicy);

  if (error)
    return (
      <p role="alert">
        Could not load {claimId}: {error}
      </p>
    );
  if (!claim) return <p>Loading {claimId}</p>;

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <header className="claim-header">
        <h1>
          <span className="mono">{claim.claim_id}</span> {claim.summary}
        </h1>
        <StatusBadge status={claim.status} />
      </header>
      <p className="note">
        {claim.customer_name}, {claimType(claim.claim_type)}
      </p>
      <div className="columns">
        <div>
          <DecisionPanel claim={claim} />
          <ClaimDetails claim={claim} />
        </div>
        <div>{policy && <PolicyPanel policy={policy} />}</div>
      </div>
    </>
  );
}
