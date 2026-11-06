import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  type Claim,
  type ClaimEvent,
  type Handler,
  getClaim,
  listClaimEvents,
  listHandlers,
  runClaim,
  signOffClaim,
} from "../api";
import { DecisionBadge } from "../components/DecisionBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatMoney } from "../money";

export function ClaimDetail() {
  const { claimId = "" } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [events, setEvents] = useState<ClaimEvent[]>([]);
  const [handlers, setHandlers] = useState<Handler[]>([]);
  const [selectedHandler, setSelectedHandler] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    void getClaim(claimId).then(setClaim);
    void listClaimEvents(claimId).then(setEvents);
  }, [claimId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    void listHandlers().then((rows) => {
      setHandlers(rows);
      if (rows.length > 0) setSelectedHandler(rows[0].handler_id);
    });
  }, []);

  const status = claim?.status;
  useEffect(() => {
    if (status !== "waiting" && status !== "in_progress") return;
    const id = setInterval(refresh, 1500);
    return () => {
      clearInterval(id);
    };
  }, [status, refresh]);

  async function handleRun() {
    setBusy(true);
    try {
      await runClaim(claimId);
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function handleSignOff() {
    if (!selectedHandler) return;
    setBusy(true);
    try {
      await signOffClaim(claimId, selectedHandler);
    } finally {
      setBusy(false);
      refresh();
    }
  }

  if (!claim) return <p>Loading the claim…</p>;

  return (
    <div>
      <div className="panel">
        <h1 className="mono">{claim.claim_id}</h1>
        <p>{claim.summary}</p>
        <StatusBadge status={claim.status} />
        {claim.status === "waiting" && (
          <button
            disabled={busy}
            onClick={() => {
              void handleRun();
            }}
          >
            {busy ? "Running…" : "Run"}
          </button>
        )}
      </div>

      <div className="panel">
        <h2>The claim</h2>
        <p>{claim.story}</p>
        <ul>
          {claim.items.map((item) => (
            <li key={item.description}>
              {item.description} ({item.category}) —{" "}
              <span className="mono">{formatMoney(item.amount)}</span>
            </li>
          ))}
        </ul>
        <p>
          Total claimed:{" "}
          <span className="mono">{formatMoney(claim.amount_claimed)}</span>
        </p>
        <h3>Documents</h3>
        <ul>
          {claim.documents.map((document) => (
            <li key={document.name}>
              <strong>{document.name}:</strong> {document.content}
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h2>Customer</h2>
        <p>
          {claim.customer.name} — {claim.customer.email}
        </p>
        <p>Customer since {claim.customer.customer_since}</p>
        {claim.customer.previous_claims.length > 0 && (
          <>
            <h3>Claim history</h3>
            <ul>
              {claim.customer.previous_claims.map((previous) => (
                <li key={previous.claim_id}>
                  {previous.filed_on}: {previous.summary} — {previous.outcome}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="panel">
        <h2>Policy</h2>
        <p>
          {claim.policy.plan_limits.name} plan, policy{" "}
          <span className="mono">{claim.policy.policy_id}</span>
        </p>
        <p>
          Deductible:{" "}
          <span className="mono">
            {formatMoney(claim.policy.plan_limits.deductible)}
          </span>
        </p>
      </div>

      {claim.decision && (
        <div className="panel">
          <h2>Decision</h2>
          <p>
            <DecisionBadge decision={claim.decision} />{" "}
            {claim.payout != null && (
              <span className="mono">{formatMoney(claim.payout)}</span>
            )}
          </p>
          <p>{claim.reason}</p>
          <p className="mono">{claim.reference}</p>
          {claim.paid_amount != null && (
            <p>Paid {formatMoney(claim.paid_amount)}</p>
          )}
        </div>
      )}

      {claim.status === "waiting_for_sign_off" && (
        <div className="panel">
          <h2>Sign off</h2>
          <div className="sign-off-bar">
            <select
              onChange={(event) => {
                setSelectedHandler(event.target.value);
              }}
              value={selectedHandler}
            >
              {handlers.map((handler) => (
                <option key={handler.handler_id} value={handler.handler_id}>
                  {handler.name}
                </option>
              ))}
            </select>
            <button
              disabled={busy}
              onClick={() => {
                void handleSignOff();
              }}
            >
              Sign off
            </button>
          </div>
        </div>
      )}

      <div className="panel">
        <h2>What the agent did</h2>
        {events.length === 0 ? (
          <p>Nothing yet.</p>
        ) : (
          <ul className="events">
            {events.map((event) => (
              <li key={event.created_at}>
                <time>{event.created_at}</time>
                {event.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
