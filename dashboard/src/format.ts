import type { Decision, DocumentName, Status, TodoStatus } from "./api";

export const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "waiting_for_sign_off",
  "decided",
  "left_for_handler",
];

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  waiting_for_sign_off: "Waiting for sign-off",
  decided: "Decided",
  left_for_handler: "Left for a handler",
};

export const TODO_LABELS: Record<TodoStatus, string> = {
  to_do: "To do",
  in_progress: "In progress",
  done: "Done",
  left_for_handler: "Left for a handler",
};

export const DOCUMENT_NAMES: Record<DocumentName, string> = {
  policy_wording: "Policy wording",
  claims_manual: "Claims manual",
};

export const DECISION_LABELS: Record<Decision, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});
const day = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});
const moment = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});
const clock = new Intl.DateTimeFormat("en-US", { timeStyle: "medium" });

export function money(amount: number): string {
  return dollars.format(amount);
}

/** A calendar date such as 2026-06-24, shown as Jun 24, 2026. */
export function formatDate(date: string): string {
  return day.format(new Date(date));
}

/** A moment such as 2026-11-04T17:16:44+00:00, in the reader's own time. */
export function formatMoment(timestamp: string): string {
  return moment.format(new Date(timestamp));
}

export function formatClock(timestamp: string): string {
  return clock.format(new Date(timestamp));
}

/** A code such as trip_delay, shown as Trip delay. */
export function humanize(code: string): string {
  const words = code.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
