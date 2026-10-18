import { useCallback } from "react";
import { getCustomer, getPolicy } from "./api";
import { addOnText, claimType, dateText, money } from "./format";
import type { ClaimDetail } from "./types";
import { usePolled } from "./usePolled";

export function Background({ claim }: Readonly<{ claim: ClaimDetail }>) {
  const loadPolicy = useCallback(
    () => getPolicy(claim.policy_id),
    [claim.policy_id],
  );
  const loadCustomer = useCallback(
    () => getCustomer(claim.customer_id),
    [claim.customer_id],
  );
  const { data: policy } = usePolled(loadPolicy, null);
  const { data: customer } = usePolled(loadCustomer, null);

  return (
    <>
      <section className="panel">
        <h2>Policy</h2>
        {policy ? (
          <dl className="facts">
            <dt>Policy</dt>
            <dd className="mono">{policy.policy_id}</dd>
            <dt>Plan</dt>
            <dd>{claimType(policy.plan)}</dd>
            <dt>Add-ons</dt>
            <dd>
              {policy.add_ons.length
                ? policy.add_ons.map(addOnText).join(", ")
                : "None"}
            </dd>
            <dt>Bought</dt>
            <dd>{dateText(policy.purchased_on)}</dd>
            <dt>Trip</dt>
            <dd>
              {policy.trip.destination}, {dateText(policy.trip.departs_on)} to{" "}
              {dateText(policy.trip.returns_on)}
            </dd>
            <dt>Trip cost</dt>
            <dd className="mono">{money(policy.trip.trip_cost)}</dd>
            <dt>Travelers</dt>
            <dd>{policy.travelers.join(", ")}</dd>
          </dl>
        ) : (
          <p className="muted">Loading the policy</p>
        )}
      </section>
      <section className="panel">
        <h2>Claim history</h2>
        {customer ? (
          <>
            <p className="muted">
              {customer.name}, a customer since{" "}
              {dateText(customer.customer_since)}.
            </p>
            {customer.previous_claims.length === 0 ? (
              <p>No earlier claims.</p>
            ) : (
              <ul className="history">
                {customer.previous_claims.map((previous) => (
                  <li key={previous.claim_id}>
                    <span className="mono">{previous.claim_id}</span>{" "}
                    {dateText(previous.filed_on)}:{" "}
                    {claimType(previous.claim_type)}. {previous.summary}.{" "}
                    {claimType(previous.outcome)}, {money(previous.amount_paid)}
                    .
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p className="muted">Loading the history</p>
        )}
      </section>
    </>
  );
}
