import { type Claim, type Policy, endpoints, useApi } from "./api";
import { DecisionBadge, ErrorPanel, Loading, StatusBadge } from "./components";
import { date, label, money } from "./format";

function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  const { decision, payment, sign_off: signOff } = claim;
  if (!decision) {
    return (
      <section className="panel">
        <h2>Decision</h2>
        <p className="muted">The agent has not decided this claim yet.</p>
      </section>
    );
  }
  return (
    <section className="panel decision">
      <h2>
        Decision <DecisionBadge decision={decision.decision} />
      </h2>
      <dl className="facts">
        <dt>Payout</dt>
        <dd className="mono">{money(decision.payout)}</dd>
        <dt>Policy section</dt>
        <dd>{decision.policy_section}</dd>
        <dt>Payment</dt>
        <dd>
          {payment
            ? `Paid ${money(payment.amount)} on ${date(payment.paid_at)}`
            : "Not paid"}
        </dd>
        {signOff && (
          <>
            <dt>Signed off by</dt>
            <dd>{signOff.handler_name}</dd>
          </>
        )}
      </dl>
      <h3>Reasons</h3>
      <p>{decision.reasons}</p>
      <h3>Calculation</h3>
      <p className="calculation">{decision.calculation}</p>
    </section>
  );
}

function PolicyPanel({ policy }: Readonly<{ policy: Policy | undefined }>) {
  if (!policy) return null;
  return (
    <section className="panel">
      <h2>Policy</h2>
      <dl className="facts">
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan_details.name}</dd>
        <dt>Add-ons</dt>
        <dd>
          {policy.add_ons.length
            ? policy.add_ons.map(label).join(", ")
            : "None"}
        </dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {date(policy.trip.departs_on)} to{" "}
          {date(policy.trip.returns_on)}
        </dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Purchased</dt>
        <dd>{date(policy.purchased_on)}</dd>
      </dl>
    </section>
  );
}

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <>
      <section className="panel">
        <h2>What happened</h2>
        <p className="muted">
          {label(claim.claim_type)} in {claim.incident_location} on{" "}
          {date(claim.incident_date)}, submitted {date(claim.submitted_on)}
        </p>
        <p>{claim.story}</p>
      </section>
      <section className="panel table-panel">
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
                <td>{label(item.category)}</td>
                <td className="number mono">{money(item.amount)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={2}>
                Total claimed
              </th>
              <td className="number mono">{money(claim.amount_claimed)}</td>
            </tr>
          </tfoot>
        </table>
      </section>
      <section className="panel">
        <h2>Documents</h2>
        {claim.documents.map((document) => (
          <article className="document" key={document.name}>
            <h3>
              {document.name}{" "}
              <span className="muted">{label(document.type)}</span>
            </h3>
            <p>{document.content}</p>
          </article>
        ))}
      </section>
    </>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const { data: claim, error } = useApi(endpoints.claim(claimId));
  const { data: policy } = useApi(
    claim ? endpoints.policy(claim.policy_id) : null,
  );

  if (error) return <ErrorPanel message={error} />;
  if (!claim) return <Loading what="the claim" />;

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <h1>
        <span className="mono">{claim.claim_id}</span> {claim.customer_name}{" "}
        <StatusBadge status={claim.status} />
      </h1>
      <p className="lead">{claim.summary}</p>
      <div className="columns">
        <div className="column">
          <DecisionPanel claim={claim} />
          <PolicyPanel policy={policy} />
        </div>
        <div className="column">
          <ClaimDetails claim={claim} />
        </div>
      </div>
    </>
  );
}
