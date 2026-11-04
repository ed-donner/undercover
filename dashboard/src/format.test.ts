import { expect, it } from "vitest";
import {
  formatClock,
  formatDate,
  formatMoment,
  humanize,
  money,
} from "./format";

it("shows money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0.5)).toBe("$0.50");
});

it("shows a calendar date the same everywhere", () => {
  expect(formatDate("2026-06-24")).toBe("Jun 24, 2026");
});

it("shows a moment in the reader's time", () => {
  const timestamp = "2026-11-04T17:16:44+00:00";
  expect(formatMoment(timestamp)).toMatch(/^Nov \d, 2026, \d+:\d\d [AP]M$/);
  expect(formatClock(timestamp)).toMatch(/^\d+:16:44 [AP]M$/);
});

it("turns codes into words", () => {
  expect(humanize("emergency_medical")).toBe("Emergency medical");
});
