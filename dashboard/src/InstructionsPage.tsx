import { getInstructions } from "./api";
import { Unreachable } from "./common";
import { useApi } from "./hooks";

export function InstructionsPage() {
  const { data: instructions, failed } = useApi(getInstructions);
  return (
    <>
      <h1>The agent&apos;s instructions</h1>
      <p className="muted">
        The UnderCover Agent works from these instructions: one set for running
        the queue, and one for each claim it hands to a claim agent. They
        can&apos;t be changed here.
      </p>
      {failed && <Unreachable />}
      {instructions && (
        <>
          <section className="panel" aria-label="Running the queue">
            <h2>Running the queue</h2>
            <div className="instructions">{instructions.queue}</div>
          </section>
          <section className="panel" aria-label="Working a claim">
            <h2>Working a claim</h2>
            <div className="instructions">{instructions.claim}</div>
          </section>
        </>
      )}
    </>
  );
}
