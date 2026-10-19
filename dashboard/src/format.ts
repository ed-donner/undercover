import type { Outcome, Run, Status, TodoStatus } from "./types";

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export const money = (amount: number) => dollars.format(amount);

export const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "waiting_for_sign_off",
  "decided",
  "needs_handler",
];

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  waiting_for_sign_off: "Waiting for sign-off",
  decided: "Decided",
  needs_handler: "Needs a handler",
};

export const TODO_LABELS: Record<TodoStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  left_for_handler: "Left for a handler",
};

export const RUN_LABELS: Record<Run["status"], string> = {
  running: "Running",
  finished: "Finished",
  failed: "Failed",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

export function claimType(type: string): string {
  const words = type.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function decisionText(
  decision: Outcome | null,
  payout: number | null,
): string {
  if (decision === null) return "";
  const label = OUTCOME_LABELS[decision];
  return payout ? `${label}, ${money(payout)}` : label;
}

export const dateText = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
    dateStyle: "long",
  });

export const timeText = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-US");

const ADD_ON_LABELS: Record<string, string> = {
  adventure_sports: "Adventure Sports",
  pre_existing_waiver: "Pre-Existing Condition Waiver",
  electronics_plus: "Electronics Plus",
};

export const addOnText = (addOn: string) =>
  ADD_ON_LABELS[addOn] ?? claimType(addOn);
