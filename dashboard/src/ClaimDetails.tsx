import type { Claim, History, Policy } from "./api";
import { date, label, money } from "./format";
import { useGet } from "./useGet";

function PolicyPanel({ policyId }: Readonly<{ policyId: string }>) {
  const { data: policy } = useGet<Policy>(`/api/policies/${policyId}`);
  if (!policy) return null;
  const addOns = policy.add_on_details.map((a) => a.name).join(", ");
  return (
    <section className="panel" aria-label="Policy">
      <h2>Policy</h2>
      <dl>
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan_details.name}</dd>
        <dt>Add-ons</dt>
        <dd>{addOns || "None"}</dd>
        <dt>Bought</dt>
        <dd>{date(policy.purchased_on)}</dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination}, {date(policy.trip.departs_on)} to{" "}
          {date(policy.trip.returns_on)}
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Deductible</dt>
        <dd className="mono">{money(policy.plan_details.deductible)}</dd>
      </dl>
    </section>
  );
}

function HistoryPanel({ customerId }: Readonly<{ customerId: string }>) {
  const { data: history } = useGet<History>(
    `/api/customers/${customerId}/history`,
  );
  if (!history) return null;
  return (
    <section className="panel" aria-label="Claim history">
      <h2>Claim history</h2>
      <p className="muted">Customer since {date(history.customer_since)}</p>
      {history.previous_claims.length === 0 && <p>No earlier claims.</p>}
      {history.previous_claims.map((previous) => (
        <div className="document" key={previous.claim_id}>
          <strong className="mono">{previous.claim_id}</strong>{" "}
          {date(previous.filed_on)}, {label(previous.claim_type)},{" "}
          {label(previous.outcome)}, {money(previous.amount_paid)}
          <p>{previous.summary}</p>
        </div>
      ))}
    </section>
  );
}

export function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <div>
      <section className="panel" aria-label="Claim">
        <h2>The claim</h2>
        <dl>
          <dt>Type</dt>
          <dd>{label(claim.claim_type)}</dd>
          <dt>Incident</dt>
          <dd>
            {date(claim.incident_date)}, {claim.incident_location}
          </dd>
          <dt>Submitted</dt>
          <dd>{date(claim.submitted_on)}</dd>
          <dt>Claimed</dt>
          <dd className="mono">{money(claim.amount_claimed)}</dd>
        </dl>
        <h3 style={{ marginTop: "1.25rem" }}>Story</h3>
        <p>{claim.story}</p>
        <h3>Items</h3>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{label(item.category)}</td>
                <td className="amount mono">{money(item.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel" aria-label="Documents">
        <h2>Documents</h2>
        {claim.documents.map((document) => (
          <div className="document" key={document.name}>
            <strong>{document.name}</strong>
            <p>{document.content}</p>
          </div>
        ))}
      </section>
      <PolicyPanel policyId={claim.policy_id} />
      <HistoryPanel customerId={claim.customer_id} />
    </div>
  );
}
