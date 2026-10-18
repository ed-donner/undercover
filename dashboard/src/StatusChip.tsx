import { STATUS_LABELS } from "./format";
import type { Status } from "./types";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return <span className={`chip chip-${status}`}>{STATUS_LABELS[status]}</span>;
}
