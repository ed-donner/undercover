import { useEffect, useState } from "react";
import { getJson, label, money, type ClaimDetail } from "./api";

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getJson<ClaimDetail>(`/api/claims/${claimId}`)
      .then(setClaim)
      .catch(() => {
        setFailed(true);
      });
  }, [claimId]);

  if (failed) return <p role="alert">Claim {claimId} could not be loaded.</p>;
  if (claim === null) return <p>Loading.</p>;

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <section className="panel">
        <h2 className="mono">{claim.claim_id}</h2>
        <p>{claim.summary}</p>
        <p>
          {label(claim.claim_type)}, claimed {money(claim.amount_claimed)},{" "}
          {label(claim.status)}, attempts {claim.attempts}
        </p>
        {claim.decision && (
          <>
            <h3>Decision</h3>
            <p>
              {label(claim.decision.decision)}, payout{" "}
              {money(claim.decision.payout)}
              {claim.payment ? ", paid" : ", not paid"}
            </p>
            <p>
              {claim.decision.reason} (relied on: {claim.decision.section})
            </p>
          </>
        )}
      </section>
      <section className="panel">
        <h3>Sections read</h3>
        {claim.reads.length === 0 ? (
          <p>No sections read.</p>
        ) : (
          <ul>
            {claim.reads.map((read) => (
              <li key={`${read.document}-${String(read.number)}`}>
                {label(read.document)} section {String(read.number)}:{" "}
                {read.title}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="panel">
        <h3>Steps</h3>
        {claim.steps.length === 0 ? (
          <p>No steps recorded.</p>
        ) : (
          <ol>
            {claim.steps.map((step) => (
              <li key={`${step.at}-${step.tool}-${step.summary}`}>
                <span className="mono">{step.tool}</span> {step.summary}
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}
