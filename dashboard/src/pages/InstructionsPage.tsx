import { useCallback, useState } from "react";
import { fetchClaimInstructions, fetchQueueInstructions } from "../api";
import { LoadError } from "../components/LoadError";
import { usePolling } from "../usePolling";

export function InstructionsPage() {
  const [queueInstructions, setQueueInstructions] = useState("");
  const [claimInstructions, setClaimInstructions] = useState("");

  const load = useCallback(
    () =>
      Promise.all([
        fetchQueueInstructions().then(setQueueInstructions),
        fetchClaimInstructions().then(setClaimInstructions),
      ]),
    [],
  );
  const failed = usePolling(load, false);

  return (
    <main className="panel">
      <h1>The agent's instructions</h1>
      {failed && <LoadError />}

      <h2>Working the queue</h2>
      <pre>{queueInstructions}</pre>

      <h2>Deciding a claim</h2>
      <pre>{claimInstructions}</pre>
    </main>
  );
}
