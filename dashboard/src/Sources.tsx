import { useCallback, useState } from "react";
import { documentsApi } from "./api";
import { useResource } from "./useResource";
import type { SectionInfo, SourceRead } from "./types";

export function ClaimSources({ reads }: { readonly reads: SourceRead[] }) {
  const attempts = [...new Set(reads.map((read) => read.run_id))];
  return (
    <section className="panel" aria-labelledby="sources-title">
      <h3 id="sources-title">Sources read</h3>
      <p className="muted">
        Complete sections delivered to the helper, grouped by attempt.
      </p>
      {reads.length === 0 && (
        <p className="muted">No source sections read yet.</p>
      )}
      {attempts.map((attempt) => (
        <div key={attempt}>
          <h4 className="mono">Attempt {attempt}</h4>
          {reads
            .filter((read) => read.run_id === attempt)
            .map((read) => (
              <details className="document" key={read.sequence}>
                <summary>
                  {read.document_id === "manual"
                    ? "Claims manual"
                    : "Policy wording"}{" "}
                  {read.version} · {read.section}. {read.title}
                  <span>Read {read.read_at}</span>
                </summary>
                <p className="document-text">{read.text}</p>
              </details>
            ))}
        </div>
      ))}
    </section>
  );
}

function LibrarySection({ section }: { readonly section: SectionInfo }) {
  const load = useCallback(
    () => documentsApi.section(section.document_id, section.section),
    [section.document_id, section.section],
  );
  const resource = useResource(load, 30000);
  return (
    <div>
      {resource.error && (
        <p className="error" role="alert">
          {resource.error}
          <button onClick={resource.reload}>Retry section</button>
        </p>
      )}
      {resource.data ? (
        <pre className="wording">{resource.data.text}</pre>
      ) : (
        !resource.error && <p role="status">Loading section…</p>
      )}
    </div>
  );
}

export function SourceLibrary() {
  const catalog = useResource(documentsApi.catalog, 30000);
  const [selected, setSelected] = useState<SectionInfo>();
  return (
    <section className="panel" aria-labelledby="library-title">
      <h3 id="library-title">Source documents</h3>
      <p className="muted">
        Read only. Browsing here does not count as an agent read on a claim.
      </p>
      {catalog.error && (
        <p className="error" role="alert">
          {catalog.error}
          <button onClick={catalog.reload}>Retry source list</button>
        </p>
      )}
      {!catalog.data && !catalog.error && <p role="status">Loading sources…</p>}
      <div className="source-catalog">
        {catalog.data?.map((section) => (
          <button
            key={`${section.document_id}-${String(section.section)}`}
            aria-pressed={
              selected?.document_id === section.document_id &&
              selected.section === section.section
            }
            onClick={() => {
              setSelected(section);
            }}
          >
            {section.document_id === "manual" ? "Manual" : "Wording"}{" "}
            {section.version} · {section.section}. {section.title}
          </button>
        ))}
      </div>
      {selected && (
        <LibrarySection
          key={`${selected.document_id}-${String(selected.section)}`}
          section={selected}
        />
      )}
    </section>
  );
}
