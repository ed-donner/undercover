import type { Decision, Status } from "./api";
import { DECISION_LABELS, STATUS_LABELS } from "./format";

export function StatusBadge({ status }: Readonly<{ status: Status }>) {
  return (
    <span className={`badge status-${status}`}>{STATUS_LABELS[status]}</span>
  );
}

export function DecisionLabel({ decision }: Readonly<{ decision: Decision }>) {
  return (
    <span className={`decision decision-${decision}`}>
      {DECISION_LABELS[decision]}
    </span>
  );
}

export function Unreachable() {
  return (
    <p role="alert" className="alert">
      Can&apos;t reach the claims system.
    </p>
  );
}
