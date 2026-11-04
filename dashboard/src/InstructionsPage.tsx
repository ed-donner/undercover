import { useEffect, useState } from "react";
import { getJson, type Instructions } from "./api";

export function InstructionsPage() {
  const [instructions, setInstructions] = useState<Instructions | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getJson<Instructions>("/api/instructions")
      .then(setInstructions)
      .catch(() => {
        setFailed(true);
      });
  }, []);

  if (failed) return <p role="alert">The instructions could not be loaded.</p>;
  if (instructions === null) return <p>Loading.</p>;

  return (
    <>
      <section className="panel">
        <h2>Queue runner instructions</h2>
        <pre>{instructions.queue_runner}</pre>
      </section>
      <section className="panel">
        <h2>Claim instructions</h2>
        <pre>{instructions.claim}</pre>
      </section>
    </>
  );
}
