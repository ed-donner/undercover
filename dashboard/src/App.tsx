import { useCallback, useEffect, useState } from "react";
import {
  ActionPanel,
  InstructionsPanel,
  OrderCard,
  ProgressCard,
  QueuePanel,
  RecommendationCard,
  RequestOverview,
  ReviewRecord,
} from "./components";
import type { Outcome, QueueItem, RequestDetail } from "./types";
import "./app.css";

type QueueState = "loading" | "ready" | "error";

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
  const [instructions, setInstructions] = useState<string | null>(null);
  const [queueState, setQueueState] = useState<QueueState>("loading");
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

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
      const result = await getJson<{ instructions: string }>(
        "/api/agent/instructions",
      );
      setInstructions(result.instructions);
    } catch {
      setInstructions("Agent instructions are unavailable.");
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
    }, 0);
    return () => {
      window.clearTimeout(timer);
    };
  }, [loadInstructions, loadQueue]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (selectedId) void loadDetail(selectedId);
      else setDetail(null);
    }, 0);
    return () => {
      window.clearTimeout(timer);
    };
  }, [loadDetail, selectedId]);

  const active = queue.some(
    (item) =>
      item.status === "in_progress" ||
      (processing && item.status === "waiting"),
  );

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => {
      void loadQueue();
      if (selectedId) void loadDetail(selectedId);
    }, 1500);
    return () => {
      window.clearInterval(timer);
    };
  }, [active, loadDetail, loadQueue, selectedId]);

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

  function initiateProcessing() {
    setProcessing(true);
    void post("/api/requests/run", "Processing started for every request.");
  }

  function recordReview(outcome: Outcome, notes: string) {
    if (!selectedId) return;
    void post(`/api/requests/${selectedId}/review`, "Review recorded.", {
      outcome,
      notes,
    });
  }

  function refreshQueue() {
    void loadQueue();
  }

  const selected = queue.find((item) => item.request_id === selectedId);

  return (
    <main className="shell">
      <Header
        busy={busy || active}
        onInitiate={initiateProcessing}
        onRefresh={refreshQueue}
      />
      {message && (
        <div className="notice" role="status">
          {message}
        </div>
      )}
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
              <RequestOverview detail={detail} orderId={selected.order_id} />
              <OrderCard detail={detail} />
              {detail.recommendation && (
                <RecommendationCard recommendation={detail.recommendation} />
              )}
              <ProgressCard detail={detail} />
              <ReviewRecord detail={detail} />
              <ActionPanel
                detail={detail}
                busy={busy}
                onReview={recordReview}
              />
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
  onInitiate: () => void;
  onRefresh: () => void;
}

function Header({ busy, onInitiate, onRefresh }: Readonly<HeaderProps>) {
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

function chooseRequest(items: QueueItem[], current: string | null) {
  if (current && items.some((item) => item.request_id === current))
    return current;
  return items[0]?.request_id ?? null;
}
