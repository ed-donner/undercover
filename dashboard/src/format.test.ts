import { expect, it } from "vitest";
import { addOnText, claimType, decisionText, money } from "./format";
import { parseRoute } from "./route";
import { settled } from "./claimPage";
import { detail, step } from "./fixtures";

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
  expect(parseRoute("#/instructions")).toEqual({ name: "instructions" });
  expect(parseRoute("#/claims/CLM-1001")).toEqual({
    name: "claim",
    id: "CLM-1001",
  });
  expect(parseRoute("#/other")).toEqual({ name: "unknown" });
});

it("settles a claim only when it is decided and the agent has finished", () => {
  const decided = detail({ status: "decided" });
  expect(settled({ claim: decided, steps: [] })).toBe(true);
  expect(settled({ claim: decided, steps: [step(1, "message", "Done")] })).toBe(
    true,
  );
  expect(settled({ claim: decided, steps: [step(1, "error", "Failed")] })).toBe(
    true,
  );
  expect(
    settled({ claim: decided, steps: [step(1, "tool_result", "{}")] }),
  ).toBe(false);
  expect(settled({ claim: detail(), steps: [] })).toBe(false);
});

it("names add-ons", () => {
  expect(addOnText("pre_existing_waiver")).toBe(
    "Pre-Existing Condition Waiver",
  );
  expect(addOnText("new_thing")).toBe("New thing");
});
