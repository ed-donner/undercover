import type { Decision } from "../api";

const DECISION_LABELS: Record<Decision, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

export function DecisionBadge({ decision }: { readonly decision: Decision }) {
  return (
    <span className={`badge badge-${decision}`}>
      {DECISION_LABELS[decision]}
    </span>
  );
}
