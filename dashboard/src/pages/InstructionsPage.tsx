import { useEffect, useState } from "react";
import { fetchInstructions } from "../api";

export function InstructionsPage() {
  const [instructions, setInstructions] = useState("");

  useEffect(() => {
    void fetchInstructions().then(setInstructions);
  }, []);

  return (
    <main className="panel">
      <h1>The agent's instructions</h1>
      <pre>{instructions}</pre>
    </main>
  );
}
