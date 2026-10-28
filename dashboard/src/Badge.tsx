import type { ClaimStatus } from "./api";
import { STATUS_LABELS } from "./format";

export function Badge({ status }: Readonly<{ status: ClaimStatus }>) {
  return (
    <span className={`badge badge-${status}`}>{STATUS_LABELS[status]}</span>
  );
}
