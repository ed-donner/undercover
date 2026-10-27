import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { fetchClaim } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { Claim } from "../types";

export function ClaimPage() {
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);

  useEffect(() => {
    if (!claimId) return;
    void fetchClaim(claimId).then(setClaim);
  }, [claimId]);

  if (!claim) {
    return <main className="panel">Loading…</main>;
  }

  return (
    <main className="panel">
      <h1>
        {claim.claim_id} <StatusBadge status={claim.status} />
      </h1>

      <h2>The story</h2>
      <p>{claim.story}</p>

      <h2>Items claimed</h2>
      <ul>
        {claim.items.map((item) => (
          <li key={item.description}>
            {item.description}: ${item.amount.toFixed(2)}
          </li>
        ))}
      </ul>

      <h2>The policy</h2>
      <p>
        {claim.policy.plan} plan, trip to {claim.policy.trip.destination} (
        {claim.policy.trip.departs_on} to {claim.policy.trip.returns_on})
      </p>

      <h2>The customer's previous claims</h2>
      {claim.customer_previous_claims.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {claim.customer_previous_claims.map((previous) => (
            <li key={previous.claim_id}>
              {previous.summary} — {previous.outcome}
            </li>
          ))}
        </ul>
      )}

      {claim.decision && (
        <>
          <h2>The decision</h2>
          <p>
            {claim.decision}
            {claim.payout !== null && claim.payout > 0
              ? `, $${claim.payout.toFixed(2)}`
              : ""}
          </p>
          <p>{claim.reason}</p>
          <p>{claim.policy_reference}</p>
        </>
      )}
    </main>
  );
}
