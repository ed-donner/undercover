import { getInstructions } from "./api";
import { Unreachable } from "./common";
import { useApi } from "./hooks";

export function InstructionsPage() {
  const { data: instructions, failed } = useApi(getInstructions);
  return (
    <>
      <h1>The agent&apos;s instructions</h1>
      <p className="muted">
        The UnderCover Agent works from these instructions. They can&apos;t be
        changed here.
      </p>
      {failed && <Unreachable />}
      {instructions && (
        <section className="panel" aria-label="Instructions">
          <div className="instructions">{instructions.text}</div>
        </section>
      )}
    </>
  );
}
