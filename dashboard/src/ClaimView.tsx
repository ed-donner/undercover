import { useCallback, useEffect, useState } from "react";
import { api, message, type Claim, type Step } from "./api";
import { ClaimDetails } from "./ClaimDetails";
import { DecisionPanel } from "./DecisionPanel";
import { StatusChip } from "./StatusChip";
import { Steps } from "./Steps";

const POLL_MS = 1000;
const START_POLLS = 10;

export function ClaimView({ claimId }: Readonly<{ claimId: string }>) {
  const [claim, setClaim] = useState<Claim>();
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [startPolls, setStartPolls] = useState(0);

  const show = (problem: unknown) => {
    setError(message(problem));
  };

  const apply = useCallback(([latest, latestSteps]: [Claim, Step[]]) => {
    setClaim(latest);
    setSteps(latestSteps);
    if (latest.status !== "waiting") setStartPolls(0);
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

  const polling = claim?.status === "in_progress" || startPolls > 0;
  useEffect(() => {
    if (!polling) return;
    const timer = setInterval(() => {
      setStartPolls((left) => Math.max(0, left - 1));
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

  const runAgent = () =>
    perform(async () => {
      await api.runAgent(claimId);
      setStartPolls(START_POLLS);
    });
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
          <button
            type="button"
            disabled={busy || polling}
            onClick={() => void runAgent()}
          >
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
          <Steps steps={steps} working={polling} />
        </div>
      </div>
    </>
  );
}
