import type { RunStatus, Status, TodoStatus } from "./api";

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export const money = (amount: number) => dollars.format(amount);

export function date(iso: string) {
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function label(code: string) {
  const words = code.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  awaiting_signoff: "Waiting for sign-off",
  decided: "Decided",
  needs_handler: "Left for a handler",
};

export const STATUSES = Object.keys(STATUS_LABELS) as Status[];

export const TODO_LABELS: Record<TodoStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
  handler: "Left for a handler",
};

export const RUN_LABELS: Record<RunStatus, string> = {
  running: "Running",
  finished: "Finished",
  failed: "Failed",
};

export function time(iso: string) {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function section(wording: string, reference: string) {
  const number = /\d+/.exec(reference)?.[0];
  if (number === undefined) return undefined;
  const part = wording.split(/^## /m).find((p) => p.startsWith(`${number}.`));
  return part === undefined ? undefined : `## ${part.trim()}`;
}
