import { expect, it } from "vitest";
import { formatMoney, parseCents, toWireAmount } from "./money";

it.each([
  ["0.00", 0],
  ["0.07", 7],
  ["1234.50", 123450],
  ["19.99", 1999],
])("reads %s as %i cents and writes it back", (wire, cents) => {
  expect(parseCents(wire)).toBe(cents);
  expect(toWireAmount(cents)).toBe(wire);
});

it("formats cents for people with separators", () => {
  expect(formatMoney(123450)).toBe("$1,234.50");
  expect(formatMoney(5)).toBe("$0.05");
});
