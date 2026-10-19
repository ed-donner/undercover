import { getClaim, listSteps } from "./api";
import type { ClaimDetail, Step } from "./types";

export interface ClaimPage {
  claim: ClaimDetail;
  steps: Step[];
}

export async function loadClaimPage(claimId: string): Promise<ClaimPage> {
  const [claim, steps] = await Promise.all([
    getClaim(claimId),
    listSteps(claimId),
  ]);
  return { claim, steps };
}

/** A decided or abandoned claim is settled once the agent's last step is its closing message or an error. */
export function settled({ claim, steps }: ClaimPage): boolean {
  const last = steps.at(-1);
  return (
    (claim.status === "decided" || claim.status === "needs_handler") &&
    (last === undefined || last.kind === "message" || last.kind === "error")
  );
}
