import type { ClaimState } from "./api";
import { stateLabel } from "./format";

export function StateBadge({ state }: Readonly<{ state: ClaimState }>) {
  return (
    <span className={`badge ${state.replaceAll(" ", "-")}`}>
      {stateLabel[state]}
    </span>
  );
}
