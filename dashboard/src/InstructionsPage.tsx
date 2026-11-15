import type { Instructions } from "./api";
import { useFetch } from "./useFetch";

export function InstructionsPage() {
  const instructions = useFetch<Instructions>("/api/instructions").data;
  if (!instructions) return <p className="muted">Loading instructions.</p>;
  return (
    <>
      <section className="panel">
        <h2>Running the queue</h2>
        <pre>{instructions.queue}</pre>
      </section>
      <section className="panel">
        <h2>Working a claim</h2>
        <pre>{instructions.claim}</pre>
      </section>
    </>
  );
}
