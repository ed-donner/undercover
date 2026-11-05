import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listClaims, runClaim, type ClaimSummary } from "../api";
import { DecisionBadge } from "../components/DecisionBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatMoney } from "../money";

export function Queue() {
  const [claims, setClaims] = useState<ClaimSummary[] | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  const refresh = useCallback(() => {
    void listClaims().then(setClaims);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const isBusy =
    running !== null ||
    (claims?.some((c) => c.status === "in_progress") ?? false);

  useEffect(() => {
    if (!isBusy) return;
    const id = setInterval(refresh, 1500);
    return () => {
      clearInterval(id);
    };
  }, [isBusy, refresh]);

  async function handleRun(claimId: string) {
    setRunning(claimId);
    try {
      await runClaim(claimId);
    } finally {
      setRunning(null);
      refresh();
    }
  }

  if (!claims) return <p>Loading the queue…</p>;

  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Type</th>
            <th>Submitted</th>
            <th>Amount claimed</th>
            <th>Status</th>
            <th>Decision</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>
                <Link className="mono" to={`/claims/${claim.claim_id}`}>
                  {claim.claim_id}
                </Link>
                <div>{claim.summary}</div>
              </td>
              <td>{claim.claim_type}</td>
              <td>{claim.submitted_on}</td>
              <td className="mono">{formatMoney(claim.amount_claimed)}</td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
              <td>
                {claim.decision ? (
                  <>
                    <DecisionBadge decision={claim.decision} />{" "}
                    {claim.payout != null && (
                      <span className="mono">{formatMoney(claim.payout)}</span>
                    )}
                  </>
                ) : (
                  "—"
                )}
              </td>
              <td>
                {claim.status === "waiting" && (
                  <button
                    disabled={running === claim.claim_id}
                    onClick={() => {
                      void handleRun(claim.claim_id);
                    }}
                  >
                    {running === claim.claim_id ? "Running…" : "Run"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
