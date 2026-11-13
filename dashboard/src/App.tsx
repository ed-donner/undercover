import { useState } from "react";
import { api, useResource } from "./api";
import { ClaimWorkspace, Instructions } from "./ClaimWorkspace";
import { money, statuses, words } from "./display";
import type { AgentRun, QueueEntry, QueueStatus } from "./types";
import { QueueRunPanel } from "./QueueRunPanel";
import "./styles.css";

const loadQueue = () => api<QueueEntry[]>("/claims");
const loadRuns = () => api<AgentRun[]>("/agent-runs");
const stateKeys = Object.keys(statuses) as QueueStatus[];

export function App() {
  const queue = useResource(loadQueue);
  const runs = useResource(loadRuns);
  const [view, setView] = useState<"claims" | "instructions">("claims");
  const [selected, setSelected] = useState<string>();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const claims = queue.data ?? [];
  const visible = claims.filter(
    (claim) =>
      (!filter || claim.status === filter) &&
      `${claim.claim_id} ${claim.customer_name} ${claim.summary}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const activeId = selected ?? visible[0]?.claim_id;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to claims
      </a>
      <header className="masthead">
        <a className="brand" href="#main">
          <span className="brand-mark" aria-hidden="true">
            u
          </span>
          UnderCover<span className="brand-divider">/</span>
          <span className="brand-subtitle">Claims operations</span>
        </a>
        <span className="pilot-label">
          <span className="pulse" /> Pilot workspace
        </span>
      </header>
      <nav className="main-nav" aria-label="Main navigation">
        <button
          aria-pressed={view === "claims"}
          onClick={() => {
            setView("claims");
          }}
        >
          Claims queue <span className="count">{claims.length}</span>
        </button>
        <button
          aria-pressed={view === "instructions"}
          onClick={() => {
            setView("instructions");
          }}
        >
          Agent instructions
        </button>
        <span className="nav-note">Every claim. A considered decision.</span>
      </nav>
      <main id="main">
        <PageHeading />
        {view === "instructions" ? (
          <Instructions />
        ) : (
          <>
            <QueueRunPanel
              runs={runs.data}
              error={runs.error}
              eligible={
                claims.filter(
                  (claim) => claim.status === "waiting" && !claim.needs_handler,
                ).length
              }
              reload={runs.reload}
              select={setSelected}
            />
            <section className="stats" aria-label="Queue overview">
              {stateKeys.map((status) => (
                <div className={`stat ${status}`} key={status}>
                  <span>{statuses[status]}</span>
                  <strong>
                    {claims
                      .filter((claim) => claim.status === status)
                      .length.toString()
                      .padStart(2, "0")}
                  </strong>
                </div>
              ))}
            </section>
            {queue.error && (
              <div className="error" role="alert">
                {queue.error}{" "}
                <button onClick={queue.reload}>Retry queue</button>
              </div>
            )}
            {!queue.data && !queue.error && <p role="status">Loading queue…</p>}
            {queue.data && (
              <div className="desk-layout">
                <aside
                  className="queue-panel panel"
                  aria-labelledby="queue-title"
                >
                  <div className="section-title">
                    <h2 id="queue-title">Claims queue</h2>
                    <span className="muted">{visible.length} claims</span>
                  </div>
                  <label className="sr-only" htmlFor="search">
                    Search claims
                  </label>
                  <input
                    id="search"
                    type="search"
                    placeholder="Search name or claim ID"
                    value={search}
                    onChange={(event) => {
                      setSearch(event.target.value);
                    }}
                  />
                  <label className="sr-only" htmlFor="status-filter">
                    Filter by status
                  </label>
                  <select
                    id="status-filter"
                    value={filter}
                    onChange={(event) => {
                      setFilter(event.target.value);
                    }}
                  >
                    <option value="">All statuses</option>
                    {stateKeys.map((status) => (
                      <option key={status} value={status}>
                        {statuses[status]}
                      </option>
                    ))}
                  </select>
                  <div className="queue-list">
                    {visible.map((claim) => (
                      <button
                        className={`claim-card ${activeId === claim.claim_id ? "selected" : ""}`}
                        key={claim.claim_id}
                        aria-pressed={activeId === claim.claim_id}
                        onClick={() => {
                          setSelected(claim.claim_id);
                        }}
                      >
                        <span className="card-top">
                          <span className="mono">{claim.claim_id}</span>
                          <span className={`status ${claim.status}`}>
                            {statuses[claim.status]}
                          </span>
                          {claim.needs_handler && (
                            <span className="handler-label">
                              Handler review
                            </span>
                          )}
                        </span>
                        <strong>{claim.customer_name}</strong>
                        <span className="claim-summary">{claim.summary}</span>
                        <span className="card-bottom">
                          <span>{words(claim.claim_type)}</span>
                          <span className="mono">
                            {money(claim.amount_claimed)}
                          </span>
                        </span>
                      </button>
                    ))}
                    {visible.length === 0 && (
                      <p className="empty-queue">
                        {claims.length === 0
                          ? "No claims in the queue."
                          : "No matching claims."}
                      </p>
                    )}
                  </div>
                  <p className="queue-footnote">
                    All amounts in USD · Updates automatically
                  </p>
                </aside>
                {activeId ? (
                  <ClaimWorkspace
                    key={activeId}
                    id={activeId}
                    onChange={queue.reload}
                    runActive={runs.data?.[0]?.status === "running"}
                  />
                ) : (
                  <div className="panel empty-state">
                    <p>Select a claim to review its evidence.</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
      <footer>
        UnderCover Travel Insurance
        <span>Local pilot · No real payments · No customer messages</span>
      </footer>
    </div>
  );
}

function PageHeading() {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">The claims desk</span>
        <h1>
          A clearer path to <em>a decision.</em>
        </h1>
      </div>
      <p>
        Review the evidence. Follow the agent.
        <br />
        Keep judgment in the right hands.
      </p>
    </div>
  );
}
