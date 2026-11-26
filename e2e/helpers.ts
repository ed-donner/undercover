import type { APIRequestContext } from "@playwright/test";
import { expect } from "@playwright/test";

export async function decide(
  request: APIRequestContext,
  claimId: string,
  decision: "approve" | "decline" | "refer",
  payout: number,
) {
  expect((await request.post(`/api/claims/${claimId}/start`)).ok()).toBe(true);
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision,
      payout,
      reason: `The agent's reason for ${claimId}.`,
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  expect(response.ok()).toBe(true);
}
