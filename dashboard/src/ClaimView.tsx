import { useCallback, useEffect, useState } from "react";
import { api, message, type Claim, type Step } from "./api";
import { ClaimDetails } from "./ClaimDetails";
import { DecisionPanel } from "./DecisionPanel";
import { StatusChip } from "./StatusChip";
import { Steps } from "./Steps";

const POLL_MS = 1000;

export function ClaimView({ claimId }: Readonly<{ claimId: string }>) {
  const [claim, setClaim] = useState<Claim>();
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const show = (problem: unknown) => {
    setError(message(problem));
  };

  const apply = useCallback(([latest, latestSteps]: [Claim, Step[]]) => {
    setClaim(latest);
    setSteps(latestSteps);
  }, []);

  const refresh = useCallback(
    () =>
      Promise.all([api.getClaim(claimId), api.listSteps(claimId)]).then(apply),
    [claimId, apply],
  );

  useEffect(() => {
    Promise.all([api.getClaim(claimId), api.listSteps(claimId)]).then(
      apply,
      show,
    );
  }, [claimId, apply]);

  const polling =
    claim?.status === "waiting" || claim?.status === "in_progress";
  useEffect(() => {
    if (!polling) return;
    const timer = setInterval(() => {
      refresh().catch(show);
    }, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [polling, refresh]);

  const perform = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(undefined);
    try {
      await action();
      await refresh();
    } catch (problem) {
      show(problem);
    } finally {
      setBusy(false);
    }
  };

  if (!claim) {
    return error ? (
      <p className="alert">{error}</p>
    ) : (
      <p className="muted">Loading the claim...</p>
    );
  }

  const runAgent = () => perform(() => api.runAgent(claimId));
  const signOff = (handlerId: string) =>
    perform(async () => {
      await api.signOff(claimId, handlerId);
      await api.pay(claimId, claim.payout ?? 0);
    });

  return (
    <>
      <p>
        <a href="#/">Back to the queue</a>
      </p>
      <div className="claim-title">
        <h1 className="mono">{claim.claim_id}</h1>
        <StatusChip status={claim.status} />
        {claim.status === "waiting" && (
          <button type="button" disabled={busy} onClick={() => void runAgent()}>
            Run agent
          </button>
        )}
      </div>
      <p className="tagline">{claim.summary}</p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="grid">
        <ClaimDetails claim={claim} />
        <div>
          <DecisionPanel
            claim={claim}
            busy={busy}
            onSignOff={(handlerId) => void signOff(handlerId)}
          />
          <Steps steps={steps} working={claim.status === "in_progress"} />
        </div>
      </div>
    </>
  );
}
