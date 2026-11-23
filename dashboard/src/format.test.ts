import { expect, it } from "vitest";
import { errorText, money, sentence } from "./format";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0.5)).toBe("$0.50");
});

it("turns a code into a sentence", () => {
  expect(sentence("trip_delay")).toBe("Trip delay");
});

it("reads an error as text", () => {
  expect(errorText(new Error("It broke"))).toBe("It broke");
  expect(errorText("odd")).toBe("odd");
});
