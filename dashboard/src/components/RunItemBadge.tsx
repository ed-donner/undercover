import type { RunItemStatus } from "../types";

const BACKGROUND: Record<RunItemStatus, string> = {
  "to do": "var(--sea-green)",
  "in progress": "var(--marigold)",
  done: "var(--cerulean)",
  "left for a handler": "var(--raspberry)",
};

const INK: Record<RunItemStatus, string> = {
  "to do": "var(--midnight)",
  "in progress": "var(--midnight)",
  done: "#ffffff",
  "left for a handler": "#ffffff",
};

export function RunItemBadge({ status }: Readonly<{ status: RunItemStatus }>) {
  return (
    <span
      className="status-badge"
      style={{ background: BACKGROUND[status], color: INK[status] }}
    >
      {status}
    </span>
  );
}
