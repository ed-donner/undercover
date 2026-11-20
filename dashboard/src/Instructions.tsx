import { documentsApi, instructionsApi } from "./api";
import { SourceLibrary } from "./Sources";
import { useResource } from "./useResource";

function InstructionPanel({ kind }: { readonly kind: "queue" | "claim" }) {
  const resource = useResource(instructionsApi[kind], 30000);
  const label = kind === "queue" ? "Queue" : "Claim";
  const retry =
    kind === "queue" ? "Retry queue instructions" : "Retry instructions";
  return (
    <section className="panel">
      <h3>{label} instructions</h3>
      {resource.error && (
        <p className="error" role="alert">
          {resource.error}
          <button onClick={resource.reload}>{retry}</button>
        </p>
      )}
      {resource.data ? (
        <pre className="wording">{resource.data.text}</pre>
      ) : (
        !resource.error && <p role="status">Loading {kind} instructions…</p>
      )}
    </section>
  );
}

export function Instructions() {
  const wording = useResource(documentsApi.wording, 30000);
  return (
    <div className="instructions-view">
      <header className="claim-header">
        <div>
          <span className="eyebrow">UnderCover Agent</span>
          <h2>Agent instructions & sources</h2>
          <p>
            Read only. The same instructions and source documents the agent uses
            through the API.
          </p>
        </div>
      </header>
      <InstructionPanel kind="queue" />
      <InstructionPanel kind="claim" />
      <SourceLibrary />
      <section className="panel">
        <h3>Policy wording {wording.data?.version}</h3>
        {wording.error && (
          <p className="error" role="alert">
            {wording.error}
            <button onClick={wording.reload}>Retry wording</button>
          </p>
        )}
        {wording.data ? (
          <pre className="wording">{wording.data.text}</pre>
        ) : (
          !wording.error && <p role="status">Loading policy wording…</p>
        )}
      </section>
    </div>
  );
}
