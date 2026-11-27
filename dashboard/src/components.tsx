import type { DecisionKind, Status } from "./api";
import { DECISION_LABELS, STATUS_LABELS } from "./format";

export function StatusBadge({ status }: Readonly<{ status: Status }>) {
  return (
    <span className={`badge status-${status}`}>{STATUS_LABELS[status]}</span>
  );
}

export function DecisionBadge({
  decision,
}: Readonly<{ decision: DecisionKind }>) {
  return (
    <span className={`badge decision-${decision}`}>
      {DECISION_LABELS[decision]}
    </span>
  );
}

export function Loading({ what }: Readonly<{ what: string }>) {
  return <p className="muted">Loading {what}</p>;
}

export function ErrorPanel({ message }: Readonly<{ message: string }>) {
  return (
    <p className="panel error" role="alert">
      {message}
    </p>
  );
}
