import { api } from "../api";
import { useData } from "../useData";

export function Instructions() {
  const { data, error } = useData(api.instructions);
  if (error)
    return <p role="alert">Could not load the instructions: {error}</p>;
  if (!data) return <p>Loading the instructions</p>;

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="note">
        Read only. These are the instructions the agent works from.
      </p>
      <section className="panel">
        <pre className="instructions">{data.text}</pre>
      </section>
    </>
  );
}
