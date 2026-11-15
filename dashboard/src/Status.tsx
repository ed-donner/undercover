import { STATUS_LABELS, type ClaimStatus, type TodoStatus } from "./api";

export function Status({
  status,
}: Readonly<{ status: ClaimStatus | TodoStatus }>) {
  return (
    <span className={`status status-${status}`}>{STATUS_LABELS[status]}</span>
  );
}
