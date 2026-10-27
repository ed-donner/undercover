import type { ClaimStatus } from "../types";

const BACKGROUND: Record<ClaimStatus, string> = {
  waiting: "var(--sea-green)",
  "in progress": "var(--marigold)",
  "waiting for sign-off": "var(--coral)",
  decided: "var(--cerulean)",
};

const INK: Record<ClaimStatus, string> = {
  waiting: "var(--midnight)",
  "in progress": "var(--midnight)",
  "waiting for sign-off": "var(--midnight)",
  decided: "#ffffff",
};

export function StatusBadge({ status }: Readonly<{ status: ClaimStatus }>) {
  return (
    <span
      className="status-badge"
      style={{ background: BACKGROUND[status], color: INK[status] }}
    >
      {status}
    </span>
  );
}
