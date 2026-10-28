import { api } from "./api";
import { useLoad } from "./hooks";

export function Instructions() {
  const { data, error } = useLoad(api.instructions);

  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading the instructions...</p>;

  return (
    <>
      <div className="page-head">
        <h1>Agent instructions</h1>
      </div>
      <p className="note">
        Read only. The UnderCover Agent receives these at the start of every
        run.
      </p>
      <section className="panel">
        <pre className="instructions">{data.text}</pre>
      </section>
    </>
  );
}
