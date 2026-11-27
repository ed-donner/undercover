import { endpoints, useApi } from "./api";
import { ErrorPanel, Loading } from "./components";

export function Instructions() {
  const { data, error } = useApi(endpoints.instructions());

  if (error) return <ErrorPanel message={error} />;
  if (!data) return <Loading what="the instructions" />;

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="lead">
        What the UnderCover Agent is told before it works on a claim. Read only.
      </p>
      <section className="panel instructions">{data.text}</section>
    </>
  );
}
