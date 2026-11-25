import type { RunStatus, Status, TodoStatus } from "./api";
import { RUN_LABELS, STATUS_LABELS, TODO_LABELS } from "./format";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return <span className={`chip chip-${status}`}>{STATUS_LABELS[status]}</span>;
}

export function TodoChip({ status }: Readonly<{ status: TodoStatus }>) {
  return (
    <span className={`chip chip-todo-${status}`}>{TODO_LABELS[status]}</span>
  );
}

export function RunChip({ status }: Readonly<{ status: RunStatus }>) {
  return (
    <span className={`chip chip-run-${status}`}>{RUN_LABELS[status]}</span>
  );
}
