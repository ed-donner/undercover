import { useEffect, useState } from "react";
import { fetchHandlers, signOffClaim } from "../api";
import { formatMoney } from "../money";
import { formatTime } from "../time";
import type { Claim, Handler } from "../types";

export function PaymentPanel({
  claim,
  onUpdated,
}: Readonly<{ claim: Claim; onUpdated: () => void }>) {
  const [handlers, setHandlers] = useState<Handler[]>([]);
  const waiting = claim.status === "waiting for sign-off";
  const signedOffBy = claim.signed_off_by;

  useEffect(() => {
    if (waiting || signedOffBy !== null) void fetchHandlers().then(setHandlers);
  }, [waiting, signedOffBy]);

  if (waiting) {
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

  const signer =
    handlers.find((handler) => handler.handler_id === signedOffBy)?.name ??
    signedOffBy;
  const signOff =
    signedOffBy !== null && claim.signed_off_on !== null
      ? `Signed off by ${signer ?? ""} on ${formatTime(claim.signed_off_on)}.`
      : null;

  if (claim.paid_amount !== null) {
    return (
      <section>
        <p>Paid {formatMoney(claim.paid_amount)}.</p>
        {signOff && <p>{signOff}</p>}
      </section>
    );
  }

  if (signOff) {
    return (
      <section>
        <p>{signOff}</p>
        <p>Payment in progress.</p>
      </section>
    );
  }

  return null;
}
