import { useGet } from "./useGet";

export function Instructions() {
  const { data, error } = useGet<{ instructions: string }>("/api/instructions");

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told before each claim. Read only.
      </p>
      <div className="panel">
        {error && <p className="alert">Could not load the instructions.</p>}
        {data && <pre className="instructions">{data.instructions}</pre>}
      </div>
    </>
  );
}
