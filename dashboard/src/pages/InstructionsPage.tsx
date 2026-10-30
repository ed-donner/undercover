import { useEffect, useState } from "react";
import { fetchClaimInstructions, fetchQueueInstructions } from "../api";

export function InstructionsPage() {
  const [queueInstructions, setQueueInstructions] = useState("");
  const [claimInstructions, setClaimInstructions] = useState("");

  useEffect(() => {
    void fetchQueueInstructions().then(setQueueInstructions);
    void fetchClaimInstructions().then(setClaimInstructions);
  }, []);

  return (
    <main className="panel">
      <h1>The agent's instructions</h1>

      <h2>Working the queue</h2>
      <pre>{queueInstructions}</pre>

      <h2>Deciding a claim</h2>
      <pre>{claimInstructions}</pre>
    </main>
  );
}
