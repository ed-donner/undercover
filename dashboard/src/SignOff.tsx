import { type SyntheticEvent, useState } from "react";
import { type Claim, type Handler, signOff } from "./api";
import { money } from "./format";

export function SignOff({
  claim,
  handlers,
  onSignedOff,
}: Readonly<{ claim: Claim; handlers: Handler[]; onSignedOff: () => void }>) {
  const [handlerId, setHandlerId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    signOff(claim.claim_id, handlerId).then(onSignedOff, (reason: unknown) => {
      setError(
        reason instanceof Error
          ? reason.message
          : "The sign-off didn't go through.",
      );
      setBusy(false);
    });
  };

  return (
    <form className="sign-off" onSubmit={submit}>
      <label htmlFor="handler">Handler</label>
      <select
        id="handler"
        value={handlerId}
        onChange={(event) => {
          setHandlerId(event.target.value);
        }}
      >
        <option value="">Choose a handler</option>
        {handlers
          .filter((handler) => handler.can_approve_over_limit)
          .map((handler) => (
            <option key={handler.handler_id} value={handler.handler_id}>
              {handler.name}
            </option>
          ))}
      </select>
      <button type="submit" disabled={!handlerId || busy}>
        Sign off and pay {money(claim.payout ?? 0)}
      </button>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
    </form>
  );
}
