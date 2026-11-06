import { useState } from "react";
import type { SyntheticEvent } from "react";
import type {
  Outcome,
  QueueItem,
  QueueStatus,
  Recommendation,
  RequestDetail,
} from "./types";
import { formatDate, formatMoney, humanize } from "./format";

const statusLabels: Record<QueueStatus, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  waiting_for_agent_review: "Needs review",
  decided: "Decided",
};
const outcomeLabels: Record<Outcome, string> = {
  approve: "Approve",
  decline: "Decline",
  request_information: "Request information",
};
export function StatusBadge({ status }: Readonly<{ status: QueueStatus }>) {
  return (
    <span className={`status-badge status-${status}`}>
      <i />
      {statusLabels[status]}
    </span>
  );
}

interface QueuePanelProps {
  items: QueueItem[];
  selectedId: string | null;
  state: "loading" | "ready" | "error";
  onSelect: (id: string) => void;
  onRefresh: () => void;
}

export function QueuePanel({
  items,
  selectedId,
  state,
  onSelect,
  onRefresh,
}: Readonly<QueuePanelProps>) {
  return (
    <aside className="queue-panel panel" aria-label="Support request queue">
      <div className="panel-heading queue-heading">
        <div>
          <h2>Queue</h2>
          <p>{items.length} requests</p>
        </div>
        <span className="queue-count">
          {String(items.length).padStart(2, "0")}
        </span>
      </div>
      {state === "loading" && (
        <p className="state-message">Loading requests…</p>
      )}
      {state === "error" && (
        <div className="state-message error-state" role="alert">
          <p>We could not load the support queue.</p>
          <button className="text-button" onClick={onRefresh}>
            Try again
          </button>
        </div>
      )}
      {state === "ready" && items.length === 0 && (
        <p className="state-message">There are no requests in the queue.</p>
      )}
      <div className="queue-list">
        {items.map((item) => (
          <button
            className={`queue-item ${selectedId === item.request_id ? "selected" : ""}`}
            key={item.request_id}
            onClick={() => {
              onSelect(item.request_id);
            }}
            aria-pressed={selectedId === item.request_id}
          >
            <span className="queue-item-top">
              <span className="request-id">{item.request_id}</span>
              <StatusBadge status={item.status} />
            </span>
            <span className="queue-customer">{item.customer_name}</span>
            <span className="queue-item-bottom">
              <span>{humanize(item.type)}</span>
              <span>{formatDate(item.created_at)}</span>
            </span>
            <span className="queue-order">Order {item.order_id}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

export function RequestOverview({
  detail,
  orderId,
}: Readonly<{
  detail: RequestDetail;
  orderId: string;
}>) {
  return (
    <article className="panel request-panel">
      <div className="detail-title-row">
        <div>
          <p className="eyebrow">
            {detail.request.request_id} <span className="eyebrow-dot">·</span>{" "}
            {orderId}
          </p>
          <h2>{humanize(detail.request.type)}</h2>
        </div>
        <StatusBadge status={detail.status} />
      </div>
      <div className="request-meta">
        <span>
          <small>Customer</small>
          {detail.customer.name}
        </span>
        <span>
          <small>Received</small>
          {formatDate(detail.request.created_at)} IST
        </span>
        <span>
          <small>Scope</small>
          {humanize(detail.request.requested_scope)}
        </span>
      </div>
      <div className="customer-message">
        <span className="quote-mark">“</span>
        <div>
          <p className="eyebrow">CUSTOMER MESSAGE</p>
          <p>{detail.request.customer_message}</p>
        </div>
      </div>
      {detail.request.evidence.length > 0 && (
        <div className="evidence">
          <strong>Evidence supplied</strong>
          <ul>
            {detail.request.evidence.map((item) => (
              <li key={item.reference}>
                <strong>{humanize(item.type)}:</strong> {item.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

export function OrderCard({ detail }: Readonly<{ detail: RequestDetail }>) {
  const { order } = detail;
  return (
    <article className="panel order-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">ORDER DETAILS</p>
          <h2>{order.order_id}</h2>
        </div>
        <span className="order-total">{formatMoney(order.total)}</span>
      </div>
      <div className="order-facts">
        <span>
          <small>Fulfillment</small>
          {humanize(order.fulfillment_status)}
        </span>
        <span>
          <small>Payment</small>
          {humanize(order.payment_status)} · {humanize(order.payment_method)}
        </span>
        <span>
          <small>Placed</small>
          {formatDate(order.placed_at)} IST
        </span>
        {order.delivery_window && (
          <span>
            <small>Delivery window</small>
            {formatDate(order.delivery_window.start)}–
            {formatDate(order.delivery_window.end)} IST
          </span>
        )}
      </div>
      <div className="item-list">
        {order.items.map((item) => (
          <div className="order-item" key={item.sku}>
            <span className="item-icon" aria-hidden="true">
              ▧
            </span>
            <span className="item-description">
              <strong>{item.name}</strong>
              <small>
                {item.sku} · Qty {item.quantity}
              </small>
            </span>
            <span>{formatMoney(item.line_total)}</span>
          </div>
        ))}
      </div>
      <div className="total-row">
        <span>Subtotal + delivery</span>
        <strong>{formatMoney(order.subtotal + order.delivery_fee)}</strong>
      </div>
    </article>
  );
}

export function RecommendationCard({
  recommendation,
}: Readonly<{
  recommendation: Recommendation;
}>) {
  return (
    <article className="panel recommendation-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">SHOPPIE AGENT</p>
          <h2>Recommendation</h2>
        </div>
        <span className={`outcome-pill outcome-${recommendation.outcome}`}>
          {outcomeLabels[recommendation.outcome]}
        </span>
      </div>
      {recommendation.priority_human_review && (
        <p className="priority-note">Priority human review recommended</p>
      )}
      <p className="recommendation-rationale">{recommendation.rationale}</p>
      <div className="citation-block">
        <small>POLICY REFERENCES</small>
        <ul>
          {recommendation.policy_citations.map((citation) => (
            <li key={citation}>{citation}</li>
          ))}
        </ul>
      </div>
      <p className="next-action">
        <strong>Suggested next step</strong>
        {recommendation.next_action}
      </p>
    </article>
  );
}

export function ProgressCard({ detail }: Readonly<{ detail: RequestDetail }>) {
  return (
    <article className="panel timeline-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">REQUEST ACTIVITY</p>
          <h2>Progress</h2>
        </div>
        {detail.status === "in_progress" && (
          <span className="working-indicator">
            <i /> Working
          </span>
        )}
      </div>
      {detail.steps.length === 0 ? (
        <p className="muted">No agent activity yet.</p>
      ) : (
        <ol className="timeline">
          {detail.steps.map((step, index) => (
            <li
              className="timeline-step"
              key={`${step.stage}-${step.created_at}`}
            >
              <span
                className={`timeline-dot ${index === detail.steps.length - 1 && detail.status === "in_progress" ? "active" : ""}`}
              />
              <div>
                <p>{step.message}</p>
                <time>{formatDate(step.created_at)} IST</time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

interface ActionPanelProps {
  detail: RequestDetail;
  busy: boolean;
  onRun: () => void;
  onReview: (outcome: Outcome, notes: string) => void;
}

export function ActionPanel({
  detail,
  busy,
  onRun,
  onReview,
}: Readonly<ActionPanelProps>) {
  const [outcome, setOutcome] = useState<Outcome>("approve");
  const [notes, setNotes] = useState("");

  function submitReview(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    onReview(outcome, notes);
  }

  return (
    <div className="action-panel panel">
      <div className="action-copy">
        <strong>{actionHeading(detail.status)}</strong>
        <p>
          Recommendations support your decision. No customer or order action is
          performed here.
        </p>
      </div>
      {(detail.status === "waiting" ||
        detail.status === "waiting_for_agent_review") && (
        <button className="primary-button" disabled={busy} onClick={onRun}>
          {runLabel(detail.status, busy)}
        </button>
      )}
      {detail.status === "waiting_for_agent_review" && (
        <form className="review-form" onSubmit={submitReview}>
          <label>
            Reviewed outcome
            <select
              value={outcome}
              onChange={(event) => {
                setOutcome(event.target.value as Outcome);
              }}
            >
              {Object.entries(outcomeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Notes <span className="optional">(optional)</span>
            <textarea
              value={notes}
              onChange={(event) => {
                setNotes(event.target.value);
              }}
              rows={2}
            />
          </label>
          <button className="secondary-button" disabled={busy} type="submit">
            Record support review
          </button>
        </form>
      )}
    </div>
  );
}

function actionHeading(status: QueueStatus) {
  const headings: Record<QueueStatus, string> = {
    waiting: "Ready for agent review",
    in_progress: "The agent is reviewing this request",
    waiting_for_agent_review: "Your review is required",
    decided: "Review complete",
  };
  return headings[status];
}

function runLabel(status: QueueStatus, busy: boolean) {
  if (busy) return "Starting…";
  return status === "waiting_for_agent_review"
    ? "Run again"
    : "Ask agent to review";
}

export function InstructionsPanel({
  instructions,
}: Readonly<{ instructions: string | null }>) {
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
      <pre>{instructions ?? "Loading instructions…"}</pre>
    </details>
  );
}

export function ReviewRecord({ detail }: Readonly<{ detail: RequestDetail }>) {
  if (!detail.review) return null;
  return (
    <article className="panel review-record">
      <p className="eyebrow">SUPPORT REVIEW RECORDED</p>
      <h2>{outcomeLabels[detail.review.outcome]}</h2>
      <p>{detail.review.notes || "No review notes added."}</p>
      <small>{formatDate(detail.review.reviewed_at)} IST</small>
    </article>
  );
}
