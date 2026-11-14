import type { Status } from "./api";
import { STATUS_LABELS } from "./format";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return <span className={`chip chip-${status}`}>{STATUS_LABELS[status]}</span>;
}
