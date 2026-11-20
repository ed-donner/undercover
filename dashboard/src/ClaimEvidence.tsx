import { money, words } from "./display";
import type { Claim, Customer, PlanDetails, Policy } from "./types";

export function ClaimEvidence({ claim }: { readonly claim: Claim }) {
  return (
    <section className="panel evidence" aria-labelledby="evidence-title">
      <div className="section-title">
        <h3 id="evidence-title">The claim</h3>
        <span className="eyebrow">Customer account</span>
      </div>
      <p className="story">{claim.story}</p>
      <dl className="facts">
        <div>
          <dt>Incident</dt>
          <dd>{claim.incident_date}</dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>{claim.incident_location}</dd>
        </div>
        <div>
          <dt>Submitted</dt>
          <dd>{claim.submitted_on}</dd>
        </div>
      </dl>
      <h4>Items claimed</h4>
      <ul className="item-list">
        {claim.items.map((item, index) => (
          <li key={`${String(index)}-${item.description}`}>
            <span>
              {item.description}
              <small>{words(item.category)}</small>
            </span>
            <span className="mono">{money(item.amount)}</span>
          </li>
        ))}
      </ul>
      <div className="total">
        <strong>Total claimed</strong>
        <strong className="mono">{money(claim.amount_claimed)}</strong>
      </div>
      <h4>
        Supporting documents{" "}
        <span className="count">{claim.documents.length}</span>
      </h4>
      {claim.documents.map((document, index) => (
        <details key={`${String(index)}-${document.name}`} className="document">
          <summary>
            {document.name}
            <span>{words(document.type)}</span>
          </summary>
          <p className="document-text">{document.content}</p>
        </details>
      ))}
    </section>
  );
}

export function PolicyPanel({
  policy,
  plan,
}: {
  readonly policy: Policy;
  readonly plan: PlanDetails;
}) {
  return (
    <section className="panel" aria-labelledby="policy-title">
      <div className="section-title">
        <h3 id="policy-title">Policy & trip</h3>
        <span className="mono">{policy.policy_id}</span>
      </div>
      <h4>{plan.plan.name}</h4>
      <dl className="facts">
        <div>
          <dt>Destination</dt>
          <dd>{policy.trip.destination}</dd>
        </div>
        <div>
          <dt>Trip dates</dt>
          <dd>
            {policy.trip.departs_on} to {policy.trip.returns_on}
          </dd>
        </div>
        <div>
          <dt>Trip cost</dt>
          <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        </div>
        <div>
          <dt>Travelers</dt>
          <dd>{policy.travelers.join(", ")}</dd>
        </div>
        <div>
          <dt>Purchased</dt>
          <dd>{policy.purchased_on}</dd>
        </div>
        <div>
          <dt>Sold through</dt>
          <dd>{policy.sold_through}</dd>
        </div>
        <div>
          <dt>Policy status</dt>
          <dd>{policy.status}</dd>
        </div>
        <div>
          <dt>Add-ons</dt>
          <dd>{policy.add_ons.map(words).join(", ") || "None"}</dd>
        </div>
      </dl>
      <details className="document">
        <summary>Plan benefits and add-ons</summary>
        <dl className="facts">
          {Object.entries(plan.plan)
            .filter(([, value]) => typeof value === "number")
            .map(([key, value]) => (
              <div key={key}>
                <dt>{words(key)}</dt>
                <dd className="mono">
                  {key.endsWith("hours")
                    ? `${String(value)} hours`
                    : money(Number(value))}
                </dd>
              </div>
            ))}
        </dl>
        <p>
          Deductible applies to:{" "}
          {plan.deductible_applies_to.map(words).join(", ")}.
        </p>
        {plan.add_ons.map((addOn) => (
          <p key={addOn.add_on}>
            <strong>{addOn.name}.</strong> {addOn.effect}
          </p>
        ))}
        <p>
          Electronics Plus per-item limit:{" "}
          {money(plan.electronics_per_item_limit)}.
        </p>
      </details>
    </section>
  );
}

export function CustomerPanel({ customer }: { readonly customer: Customer }) {
  return (
    <section className="panel" aria-labelledby="customer-title">
      <div className="section-title">
        <h3 id="customer-title">Customer & history</h3>
        <span className="mono">{customer.customer_id}</span>
      </div>
      <h4>{customer.name}</h4>
      <dl className="facts">
        <div>
          <dt>Email</dt>
          <dd>{customer.email}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>{customer.phone}</dd>
        </div>
        <div>
          <dt>Date of birth</dt>
          <dd>{customer.date_of_birth}</dd>
        </div>
        <div>
          <dt>Address</dt>
          <dd>{Object.values(customer.address).join(", ")}</dd>
        </div>
        <div>
          <dt>Customer since</dt>
          <dd>{customer.customer_since}</dd>
        </div>
      </dl>
      <h4>Previous claims</h4>
      {customer.previous_claims.length === 0 ? (
        <p className="muted">No previous claims.</p>
      ) : (
        <ul className="history-list">
          {customer.previous_claims.map((claim) => (
            <li key={claim.claim_id}>
              <span className="mono">{claim.claim_id}</span>
              <strong>{claim.summary}</strong>
              <span>
                {words(claim.claim_type)} · Incident {claim.incident_date} ·
                Filed {claim.filed_on}
              </span>
              <span>
                {claim.outcome} · Paid{" "}
                <span className="mono">{money(claim.amount_paid)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
