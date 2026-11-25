import type { Instructions as Texts } from "./api";
import { useGet } from "./useGet";

export function Instructions() {
  const { data, error } = useGet<Texts>("/api/instructions");

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told when it runs the queue, and when it
        works each claim. Read only.
      </p>
      {error && <p className="alert">Could not load the instructions.</p>}
      {data && (
        <>
          <section className="panel" aria-label="Running the queue">
            <h2>Running the queue</h2>
            <pre className="instructions">{data.queue}</pre>
          </section>
          <section className="panel" aria-label="Working a claim">
            <h2>Working a claim</h2>
            <pre className="instructions">{data.claim}</pre>
          </section>
        </>
      )}
    </>
  );
}
