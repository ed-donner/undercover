import { useState } from "react";
import type { Claim, Handler } from "./api";
import { money, post } from "./api";
import { Status } from "./Status";
import { useFetch } from "./useFetch";

const POLL_MS = 2000;

function SignOff({
  claim,
  onDone,
}: Readonly<{ claim: Claim; onDone: () => void }>) {
  const handlers = useFetch<Handler[]>("/api/handlers").data ?? [];
  const [chosen, setChosen] = useState("");
  const handlerId = chosen || handlers[0]?.handler_id || "";

  const signOff = () => {
    const base = `/api/claims/${claim.claim_id}`;
    void post(`${base}/sign-off`, { handler_id: handlerId })
      .then(() => post(`${base}/payment`, { amount: claim.payout }))
      .then(onDone);
  };

  return (
    <div className="signoff">
      <label>
        Sign off as{" "}
        <select
          value={handlerId}
          onChange={(event) => {
            setChosen(event.target.value);
          }}
        >
          {handlers.map((handler) => (
            <option key={handler.handler_id} value={handler.handler_id}>
              {handler.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={signOff} disabled={handlerId === ""}>
        Sign off and pay {money(claim.payout)}
      </button>
    </div>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const { data: claim, reload } = useFetch<Claim>(
    `/api/claims/${claimId}`,
    POLL_MS,
  );
  if (!claim) return <p className="muted">Loading claim.</p>;
  const reads = claim.steps.filter((step) => step.kind === "read");

  return (
    <>
      <section className="panel">
        <h2>
          <span className="mono">{claim.claim_id}</span>{" "}
          <Status status={claim.status} />
        </h2>
        <p className="muted">
          {claim.claim_type.replaceAll("_", " ")}, {claim.incident_location},{" "}
          {claim.incident_date}
        </p>
        <p>{claim.story}</p>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td className="num mono">{money(item.amount)}</td>
              </tr>
            ))}
            <tr>
              <th>Claimed</th>
              <th className="num mono">{money(claim.amount_claimed)}</th>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Decision</h2>
        {claim.decision ? (
          <>
            <p>
              <strong>{claim.decision}</strong>, payout{" "}
              <span className="mono">{money(claim.payout)}</span>
              {claim.paid !== null && ", paid"}
              {claim.signed_off_by && `, signed off by ${claim.signed_off_by}`}
            </p>
            <p>{claim.reason}</p>
            <p className="muted">{claim.policy_section}</p>
            {claim.status === "awaiting_signoff" && (
              <SignOff claim={claim} onDone={reload} />
            )}
          </>
        ) : (
          <p className="muted">Not decided yet.</p>
        )}
      </section>
      <section className="panel">
        <h2>What the agent read</h2>
        {reads.length === 0 ? (
          <p className="muted">Nothing yet.</p>
        ) : (
          <ul aria-label="Sections read">
            {reads.map((step) => (
              <li key={step.created_at + step.text}>{step.text}</li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel">
        <h2>Steps</h2>
        <ol aria-label="Steps">
          {claim.steps.map((step) => (
            <li key={step.created_at + step.text}>
              <span className="muted mono">{step.kind}</span> {step.text}
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
