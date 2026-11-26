import { expect, it } from "vitest";
import { claimType, money } from "./format";
import { parseRoute } from "./router";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
});

it("turns claim types into labels", () => {
  expect(claimType("trip_delay")).toBe("Trip delay");
});

it("parses routes", () => {
  expect(parseRoute("")).toEqual({ page: "queue" });
  expect(parseRoute("#/")).toEqual({ page: "queue" });
  expect(parseRoute("#/claims/CLM-1001")).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
  expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
});
