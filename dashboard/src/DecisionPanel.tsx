import { useState } from "react";
import type { Claim, Handler } from "./api";
import { date, label, money, section } from "./format";
import { useGet } from "./useGet";

interface Props {
  claim: Claim;
  busy: boolean;
  onSignOff: (handlerId: string) => void;
}

function Payment({ claim }: Readonly<{ claim: Claim }>) {
  if (claim.paid_amount !== null && claim.paid_at !== null) {
    return (
      <p>
        Paid <span className="mono">{money(claim.paid_amount)}</span> on{" "}
        {date(claim.paid_at)}.
      </p>
    );
  }
  if (claim.decision === "approve" && claim.status === "decided") {
    return <p className="muted">Not paid yet.</p>;
  }
  return null;
}

function SignOff({ busy, onSignOff }: Readonly<Omit<Props, "claim">>) {
  const { data: handlers } = useGet<Handler[]>("/api/handlers");
  const [chosen, setChosen] = useState("");
  const able = (handlers ?? []).filter((h) => h.can_approve_over_limit);
  return (
    <div className="notice">
      <p>
        This payout is over the approval limit, so the payment waits for a
        handler&apos;s sign-off.
      </p>
      <div className="actions">
        <label>
          Handler{" "}
          <select
            value={chosen}
            onChange={(event) => {
              setChosen(event.target.value);
            }}
          >
            <option value="">Choose a handler</option>
            {able.map((handler) => (
              <option key={handler.handler_id} value={handler.handler_id}>
                {handler.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={busy || chosen === ""}
          onClick={() => {
            onSignOff(chosen);
          }}
        >
          Sign off and pay
        </button>
      </div>
    </div>
  );
}

export function DecisionPanel({ claim, busy, onSignOff }: Readonly<Props>) {
  const { data } = useGet<{ wording: string }>("/api/policy-wording");
  const { data: handlers } = useGet<Handler[]>("/api/handlers");
  if (!claim.decision) return null;
  const text =
    data && claim.policy_section
      ? section(data.wording, claim.policy_section)
      : undefined;
  const signer = handlers?.find((h) => h.handler_id === claim.signed_off_by);

  return (
    <section className="panel" aria-label="Decision">
      <h2>The agent&apos;s decision</h2>
      <p className={`decision decision-${claim.decision}`}>
        {label(claim.decision)}
        {claim.decision === "approve" && (
          <span className="mono"> {money(claim.payout ?? 0)}</span>
        )}
      </p>
      <p>{claim.reason}</p>
      <p>
        <strong>Policy section:</strong> {claim.policy_section}
      </p>
      {claim.status === "awaiting_signoff" && (
        <SignOff busy={busy} onSignOff={onSignOff} />
      )}
      {claim.signed_off_at && (
        <p>
          Signed off by {signer?.name ?? claim.signed_off_by} on{" "}
          {date(claim.signed_off_at)}.
        </p>
      )}
      <Payment claim={claim} />
      {text && (
        <details>
          <summary>The policy wording for this section</summary>
          <pre className="wording">{text}</pre>
        </details>
      )}
    </section>
  );
}
