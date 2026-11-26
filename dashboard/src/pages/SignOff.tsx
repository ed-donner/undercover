import { useCallback, useState } from "react";
import type { Claim } from "../api";
import { api } from "../api";
import { money } from "../format";
import { useData } from "../useData";

export function SignOff({
  claim,
  onSignedOff,
}: Readonly<{ claim: Claim; onSignedOff: () => void }>) {
  const { data: handlers } = useData(api.handlers);
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState<string>();
  const payout = claim.decision?.payout ?? 0;

  const signOff = useCallback(() => {
    api
      .signOff(claim.claim_id, handlerId)
      .then(onSignedOff)
      .catch((e: unknown) => {
        setError(String(e));
      });
  }, [claim.claim_id, handlerId, onSignedOff]);

  return (
    <section className="panel" aria-label="Sign-off">
      <h2>Waiting for sign-off</h2>
      <p>
        The agent approved a payout of{" "}
        <span className="mono">{money(payout)}</span>. Payouts over $1,000 are
        paid once a handler signs off.
      </p>
      <div className="signoff">
        <label htmlFor="handler">Handler</label>
        <select
          id="handler"
          value={handlerId}
          onChange={(e) => {
            setHandlerId(e.target.value);
          }}
        >
          <option value="">Choose a handler</option>
          {handlers?.map((h) => (
            <option key={h.handler_id} value={h.handler_id}>
              {h.name}
            </option>
          ))}
        </select>
        <button type="button" disabled={!handlerId} onClick={signOff}>
          Sign off and pay {money(payout)}
        </button>
      </div>
      {error && <p role="alert">Could not sign off: {error}</p>}
    </section>
  );
}
