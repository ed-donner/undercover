import { getInstructions } from "./api";
import { useData } from "./hooks";

const never = () => false;

export function Instructions() {
  const { data, error } = useData(getInstructions, never);
  if (data === undefined) return <p>{error ?? "Loading the instructions"}</p>;

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        These are the instructions the agent works from. They are read only.
      </p>
      <section className="panel instructions">
        {data
          .split("\n\n")
          .map((block) =>
            block.startsWith("## ") ? (
              <h2 key={block}>{block.slice(3)}</h2>
            ) : (
              <p key={block}>{block}</p>
            ),
          )}
      </section>
    </>
  );
}
