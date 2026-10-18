import { useState } from "react";
import { listHandlers, signOff } from "./api";
import { money } from "./format";
import type { ClaimDetail } from "./types";
import { usePolled } from "./usePolled";

export function SignOffPanel({
  claim,
  onSignedOff,
}: Readonly<{ claim: ClaimDetail; onSignedOff: () => void }>) {
  const { data: handlers } = usePolled(listHandlers, null);
  const [chosen, setChosen] = useState("");
  const [failed, setFailed] = useState(false);
  const handlerId = chosen || handlers?.[0]?.handler_id;
  const payout = claim.decision?.payout ?? 0;

  const submit = () => {
    if (!handlerId) return;
    setFailed(false);
    signOff(claim.claim_id, handlerId)
      .then(onSignedOff)
      .catch(() => {
        setFailed(true);
      });
  };

  return (
    <section className="panel signoff">
      <h2>Sign-off needed</h2>
      <p>
        The payout of <span className="mono">{money(payout)}</span> is over the
        approval limit. It is held until a handler signs off.
      </p>
      <div className="row">
        <label htmlFor="handler">Handler</label>
        <select
          id="handler"
          value={handlerId ?? ""}
          onChange={(event) => {
            setChosen(event.target.value);
          }}
        >
          {handlers?.map((handler) => (
            <option key={handler.handler_id} value={handler.handler_id}>
              {handler.name}
            </option>
          ))}
        </select>
        <button className="primary" disabled={!handlerId} onClick={submit}>
          Sign off and pay {money(payout)}
        </button>
      </div>
      {failed && (
        <p role="alert" className="alert">
          The sign-off did not go through.
        </p>
      )}
    </section>
  );
}
