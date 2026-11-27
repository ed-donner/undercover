import { expect, it } from "vitest";
import { date, label, money } from "./format";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
});

it("formats dates and timestamps as days", () => {
  expect(date("2026-06-24")).toBe("Jun 24, 2026");
  expect(date("2026-11-27 14:29:06")).toBe("Nov 27, 2026");
});

it("turns identifiers into labels", () => {
  expect(label("trip_delay")).toBe("Trip delay");
  expect(label("emergency_medical")).toBe("Emergency medical");
});
