import { toWireAmount } from "./money";
import type { Claim, ClaimSummary } from "./types";

export type FetchInput = string | URL | Request;

export function requestUrl(input: FetchInput): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

/** Serve a claim as the API does: amounts as two-decimal strings. */
export function claimToWire(claim: Claim) {
  return {
    ...claim,
    amount_claimed: toWireAmount(claim.amount_claimed),
    items: claim.items.map((item) => ({
      ...item,
      amount: toWireAmount(item.amount),
    })),
    payout: claim.payout === null ? null : toWireAmount(claim.payout),
    paid_amount:
      claim.paid_amount === null ? null : toWireAmount(claim.paid_amount),
  };
}

export function summaryToWire(summary: ClaimSummary) {
  return { ...summary, amount_claimed: toWireAmount(summary.amount_claimed) };
}
