import { getInstructions } from "./api";
import { usePolled } from "./usePolled";

export function Instructions() {
  const { data, error } = usePolled(getInstructions, null);
  if (!data) {
    return (
      <p role={error ? "alert" : "status"}>
        {error
          ? "The instructions could not be loaded."
          : "Loading the instructions"}
      </p>
    );
  }
  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        What the UnderCover Agent is told on every claim. Read only.
      </p>
      <pre className="panel instructions">{data.text}</pre>
    </>
  );
}
