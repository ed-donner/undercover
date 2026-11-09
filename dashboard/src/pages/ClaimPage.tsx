import { useCallback, useState } from "react";
import { useParams } from "react-router";
import { fetchClaim, fetchSteps, runAgent } from "../api";
import { LoadError } from "../components/LoadError";
import { PaymentPanel } from "../components/PaymentPanel";
import { StatusBadge } from "../components/StatusBadge";
import { formatMoney } from "../money";
import type { Claim, Step } from "../types";
import { usePolling } from "../usePolling";

export function ClaimPage() {
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);

  const load = useCallback(
    () =>
      Promise.all([
        fetchClaim(claimId ?? "").then(setClaim),
        fetchSteps(claimId ?? "").then(setSteps),
      ]),
    [claimId],
  );
  const failed = usePolling(load, claim?.status !== "decided");

  if (!claim) {
    return <main className="panel">{failed ? <LoadError /> : "Loading…"}</main>;
  }

  return (
    <main className="panel">
      <h1>
        <span className="mono">{claim.claim_id}</span>{" "}
        <StatusBadge status={claim.status} />
      </h1>
      {failed && <LoadError />}

      {claim.status === "waiting" && (
        <button
          onClick={() => {
            void runAgent(claim.claim_id).then(() =>
              fetchClaim(claim.claim_id).then(setClaim),
            );
          }}
          type="button"
        >
          Run agent
        </button>
      )}

      {steps.length > 0 && (
        <>
          <h2>What the agent did</h2>
          <ol>
            {steps.map((step) => (
              <li key={`${step.recorded_on} ${step.text}`}>{step.text}</li>
            ))}
          </ol>
        </>
      )}

      <h2>The story</h2>
      <p>{claim.story}</p>

      <h2>Items claimed</h2>
      <ul>
        {claim.items.map((item) => (
          <li key={item.description}>
            {item.description}:{" "}
            <span className="mono">{formatMoney(item.amount)}</span>
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
              ? `, ${formatMoney(claim.payout)}`
              : ""}
          </p>
          <p>{claim.reason}</p>
          <p>{claim.policy_reference}</p>
        </>
      )}

      <PaymentPanel
        claim={claim}
        onUpdated={() => {
          void fetchClaim(claim.claim_id).then(setClaim);
        }}
      />
    </main>
  );
}
