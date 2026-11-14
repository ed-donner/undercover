import type { Status } from "./api";

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
};

export const STATUSES = Object.keys(STATUS_LABELS) as Status[];

export function section(wording: string, reference: string) {
  const number = /\d+/.exec(reference)?.[0];
  if (number === undefined) return undefined;
  const part = wording.split(/^## /m).find((p) => p.startsWith(`${number}.`));
  return part === undefined ? undefined : `## ${part.trim()}`;
}
