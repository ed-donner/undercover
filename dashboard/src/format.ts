import type { ClaimState, DecisionKind, StepKind } from "./api";

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function money(amount: number): string {
  return dollars.format(amount);
}

export function sentence(text: string): string {
  const spaced = text.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export const stateLabel: Record<ClaimState, string> = {
  waiting: "Waiting",
  "in progress": "In progress",
  "waiting for sign-off": "Waiting for sign-off",
  decided: "Decided",
};

export const decisionLabel: Record<DecisionKind, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

export const stepLabel: Record<StepKind, string> = {
  tool_call: "Tool call",
  tool_result: "Result",
  message: "Message",
  error: "Error",
};

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
