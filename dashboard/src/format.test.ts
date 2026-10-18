import { expect, it } from "vitest";
import { claimType, decisionText, money } from "./format";
import { parseRoute } from "./route";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
});

it("makes claim types readable", () => {
  expect(claimType("emergency_medical")).toBe("Emergency medical");
});

it("describes a decision", () => {
  expect(decisionText(null, null)).toBe("");
  expect(decisionText("decline", 0)).toBe("Declined");
  expect(decisionText("approve", 200)).toBe("Approved, $200.00");
});

it("parses the route", () => {
  expect(parseRoute("")).toEqual({ name: "queue" });
  expect(parseRoute("#/")).toEqual({ name: "queue" });
  expect(parseRoute("#/other")).toEqual({ name: "unknown" });
});
