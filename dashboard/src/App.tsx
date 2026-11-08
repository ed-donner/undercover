import { useCallback, useEffect, useState } from "react";
import {
  ActionPanel,
  OrderCard,
  ProgressCard,
  QueuePanel,
  RecommendationCard,
  RequestOverview,
  RunPanel,
} from "./components";
import { formatDate } from "./format";
import type {
  Instructions,
  Outcome,
  QueueItem,
  RequestDetail,
  Run,
} from "./types";
import "./app.css";

type QueueState = "loading" | "ready" | "error";
const DEFAULT_CAP = 5;

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok)
    throw new Error(`Request failed (${String(response.status)})`);
  return response.json() as Promise<T>;
}

export function App() {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [instructions, setInstructions] = useState<Instructions | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [cap, setCap] = useState(DEFAULT_CAP);
  const [queueState, setQueueState] = useState<QueueState>("loading");
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setQueueState("loading");
    try {
      const items = await getJson<QueueItem[]>("/api/requests");
      setQueue(items);
      setQueueState("ready");
      setSelectedId((current) => chooseRequest(items, current));
    } catch {
      setQueueState("error");
    }
  }, []);

  const loadInstructions = useCallback(async () => {
    try {
      setInstructions(await getJson<Instructions>("/api/agent/instructions"));
    } catch {
      const unavailable = "Agent instructions are unavailable.";
      setInstructions({ queue: unavailable, request: unavailable });
    }
  }, []);

  const loadRun = useCallback(async () => {
    try {
      setRun(await getJson<Run | null>("/api/runs/current"));
    } catch {
      setRun(null);
    }
  }, []);

  const loadDetail = useCallback(async (requestId: string) => {
    try {
      const result = await getJson<RequestDetail>(`/api/requests/${requestId}`);
      setDetail(result);
      setDetailError(null);
    } catch {
      setDetail(null);
      setDetailError("We could not load this request. Try selecting it again.");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadQueue();
      void loadInstructions();
      void loadRun();
    }, 0);
    return () => {
      window.clearTimeout(timer);
    };
  }, [loadInstructions, loadQueue, loadRun]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (selectedId) void loadDetail(selectedId);
      else setDetail(null);
    }, 0);
    return () => {
      window.clearTimeout(timer);
    };
  }, [loadDetail, selectedId]);

  const active =
    run?.status === "running" ||
    detail?.status === "in_progress" ||
    queue.some((item) => item.status === "in_progress");

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => {
      void loadQueue();
      void loadRun();
      if (selectedId) void loadDetail(selectedId);
    }, 1500);
    return () => {
      window.clearInterval(timer);
    };
  }, [active, loadDetail, loadQueue, loadRun, selectedId]);

  async function post(url: string, done: string, body?: object) {
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (!response.ok) {
        const errorBody = (await response.json()) as { detail?: string };
        throw new Error(
          errorBody.detail ?? `Request failed (${String(response.status)})`,
        );
      }
      setMessage(done);
      await Promise.all([
        loadQueue(),
        loadRun(),
        selectedId ? loadDetail(selectedId) : Promise.resolve(),
      ]);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Something went wrong.",
      );
    } finally {
      setBusy(false);
    }
  }

  function selectRequest(id: string) {
    setSelectedId(id);
    setMessage(null);
  }

  const maxCap = Math.max(queue.length, 1);
  const runCap = Math.min(cap, maxCap);

  function initiateProcessing() {
    void post(
      "/api/runs",
      `Processing started for up to ${String(runCap)} waiting requests.`,
      { cap: runCap },
    );
  }

  function recordReview(outcome: Outcome, notes: string, reviewedBy: string) {
    if (!selectedId) return;
    void post(`/api/requests/${selectedId}/review`, "Review recorded.", {
      outcome,
      notes,
      reviewed_by: reviewedBy,
    });
  }

  const refreshQueue = () => void loadQueue();
  const selected = queue.find((item) => item.request_id === selectedId);

  return (
    <main className="shell">
      <Header
        busy={busy || active}
        cap={runCap}
        maxCap={maxCap}
        onCapChange={setCap}
        onInitiate={initiateProcessing}
        onRefresh={refreshQueue}
      />
      {message && (
        <div className="notice" role="status">
          {message}
        </div>
      )}
      <RunPanel run={run} />
      <div className="workspace">
        <QueuePanel
          items={queue}
          selectedId={selectedId}
          state={queueState}
          onSelect={selectRequest}
          onRefresh={refreshQueue}
        />
        <section className="detail-column" aria-label="Request details">
          {detailError && (
            <div className="panel state-message error-state" role="alert">
              {detailError}
            </div>
          )}
          {!detail && !detailError && (
            <div className="panel state-message">
              Select a request to see its details.
            </div>
          )}
          {detail && selected && (
            <>
              <div className="detail-grid">
                <RequestOverview detail={detail} orderId={selected.order_id} />
                <OrderCard detail={detail} />
              </div>
              {detail.recommendation && (
                <RecommendationCard recommendation={detail.recommendation} />
              )}
              <ReviewRecord detail={detail} />
              <ActionPanel
                detail={detail}
                busy={busy}
                onReview={recordReview}
              />
              <ProgressCard detail={detail} />
            </>
          )}
        </section>
      </div>
      <InstructionsPanel instructions={instructions} />
      <footer>
        <span>Shoppie Support Pilot</span>
        <span>
          Sample policies · Agent recommendations require human review
        </span>
      </footer>
    </main>
  );
}

interface HeaderProps {
  busy: boolean;
  cap: number;
  maxCap: number;
  onCapChange: (cap: number) => void;
  onInitiate: () => void;
  onRefresh: () => void;
}

function Header({
  busy,
  cap,
  maxCap,
  onCapChange,
  onInitiate,
  onRefresh,
}: Readonly<HeaderProps>) {
  return (
    <>
      <header className="topbar">
        <a className="brand" href="#queue" aria-label="Shoppie Support home">
          <span className="brand-mark">S</span>
          <span>shoppie</span>
          <span className="brand-divider">/</span>
          <span className="brand-subtitle">support desk</span>
        </a>
        <div className="topbar-meta">
          <span className="sample-pill">
            <span /> Pilot workspace
          </span>
          <span className="agent-avatar" aria-label="Support agent">
            SA
          </span>
        </div>
      </header>
      <section className="page-heading" id="queue">
        <div>
          <p className="eyebrow">CUSTOMER OPERATIONS</p>
          <h1>Support requests</h1>
          <p className="subheading">
            Review order issues and recommendations from the Shoppie Agent.
          </p>
        </div>
        <div className="heading-actions">
          <button className="secondary-button" onClick={onRefresh}>
            <span aria-hidden="true">↻</span> Refresh queue
          </button>
          <label className="cap-input">
            Requests to work
            <input
              type="number"
              min={1}
              max={maxCap}
              value={cap}
              onChange={(event) => {
                onCapChange(
                  Math.min(
                    maxCap,
                    Math.max(1, Number(event.target.value) || 1),
                  ),
                );
              }}
            />
          </label>
          <button
            className="primary-button"
            disabled={busy}
            onClick={onInitiate}
          >
            {busy ? "Processing…" : "Initiate processing"}
          </button>
        </div>
      </section>
    </>
  );
}

function InstructionsPanel({
  instructions,
}: Readonly<{ instructions: Instructions | null }>) {
  return (
    <details className="instructions-panel panel">
      <summary>
        <span>
          <span className="eyebrow">AGENT CONFIGURATION</span>
          <strong>Shoppie Agent instructions</strong>
        </span>
        <span className="read-only">
          Read only <span aria-hidden="true">＋</span>
        </span>
      </summary>
      {instructions ? (
        <>
          <h3>Running the queue</h3>
          <pre>{instructions.queue}</pre>
          <h3>Working a request</h3>
          <pre>{instructions.request}</pre>
        </>
      ) : (
        <pre>Loading instructions…</pre>
      )}
    </details>
  );
}

function ReviewRecord({ detail }: Readonly<{ detail: RequestDetail }>) {
  if (!detail.review) return null;
  const { outcome, notes, reviewed_by, reviewed_at } = detail.review;
  const titles: Record<Outcome, string> = {
    approve: "Approve",
    decline: "Decline",
    request_information: "Request information",
  };
  const badges: Record<Outcome, string> = {
    approve: "Approved",
    decline: "Declined",
    request_information: "Info requested",
  };
  return (
    <article className="panel review-record">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">SUPPORT REVIEW RECORDED</p>
          <h2>{titles[outcome]}</h2>
        </div>
        <span className={`outcome-pill outcome-${outcome}`}>
          {badges[outcome]}
        </span>
      </div>
      <p>{notes || "No review notes added."}</p>
      <small>
        Reviewed by {reviewed_by} · {formatDate(reviewed_at)} IST
      </small>
    </article>
  );
}

function chooseRequest(items: QueueItem[], current: string | null) {
  if (current && items.some((item) => item.request_id === current))
    return current;
  return items[0]?.request_id ?? null;
}
