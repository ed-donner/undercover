import { useEffect, useState } from "react";
import { fetchHandlers, payClaim, signOffClaim } from "../api";
import { formatMoney } from "../money";
import type { Claim, Handler } from "../types";

export function PaymentPanel({
  claim,
  onUpdated,
}: Readonly<{ claim: Claim; onUpdated: () => void }>) {
  const [handlers, setHandlers] = useState<Handler[]>([]);

  useEffect(() => {
    if (claim.status !== "waiting for sign-off") return;
    void fetchHandlers().then(setHandlers);
  }, [claim.status]);

  if (claim.status === "waiting for sign-off") {
    return (
      <section>
        <h2>Sign off</h2>
        <p>This payout is over the $1,000 approval limit.</p>
        {handlers.map((handler) => (
          <button
            key={handler.handler_id}
            onClick={() => {
              void signOffClaim(claim.claim_id, handler.handler_id).then(
                onUpdated,
              );
            }}
            type="button"
          >
            Sign off as {handler.name}
          </button>
        ))}
      </section>
    );
  }

  if (claim.paid_amount !== null) {
    return <p>Paid {formatMoney(claim.paid_amount)}.</p>;
  }

  if (claim.status === "decided" && claim.decision === "approve") {
    return (
      <button
        onClick={() => {
          void payClaim(claim.claim_id, claim.payout ?? 0).then(onUpdated);
        }}
        type="button"
      >
        Release payment
      </button>
    );
  }

  return null;
}
