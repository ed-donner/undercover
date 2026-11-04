import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Step } from "./api";
import { Steps } from "./Steps";
import { stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

let lastStepId = 0;

function step(kind: Step["kind"], name: string, content: string): Step {
  lastStepId += 1;
  return {
    step_id: lastStepId,
    thread_id: "thread-1",
    kind,
    name,
    content,
    created_at: "2026-11-04T17:16:44+00:00",
  };
}

it("says when the agent hasn't taken a step", async () => {
  stubApi({ "GET /api/claims/CLM-1001/steps": [] });
  render(<Steps claimId="CLM-1001" />);
  expect(await screen.findByText("No steps yet.")).toBeDefined();
});

it("shows each step the agent took", async () => {
  stubApi({
    "GET /api/claims/CLM-1001/steps": [
      step("tool_call", "get_policy", '{"policy_id": "POL-2001"}'),
      step("tool_result", "get_policy", '{"plan": "premium"}'),
      step("tool_call", "lookup_weather", "{}"),
      step("reply", "agent", "Approved $420.00 for the delay."),
    ],
  });
  render(<Steps claimId="CLM-1001" />);
  expect(await screen.findByText("Reading the policy")).toBeDefined();
  expect(screen.getByText('{"policy_id": "POL-2001"}')).toBeDefined();
  expect(screen.getByText("What get_policy returned")).toBeDefined();
  expect(screen.getByText('{"plan": "premium"}')).toBeDefined();
  expect(screen.getByText("lookup_weather")).toBeDefined();
  expect(screen.getByText("Approved $420.00 for the delay.")).toBeDefined();
  expect(screen.queryByText("Refused")).toBeNull();
});

it("points out when the claims system refused the agent", async () => {
  stubApi({
    "GET /api/claims/CLM-1003/steps": [
      step(
        "tool_result",
        "pay_claim",
        '{"detail":"A payout over $1,000.00 waits for a handler\'s sign-off."}',
      ),
      step("tool_result", "record_decision", '{"detail":[{"msg":"bad"}]}'),
    ],
  });
  render(<Steps claimId="CLM-1003" />);
  expect(
    await screen.findByText(
      "A payout over $1,000.00 waits for a handler's sign-off.",
    ),
  ).toBeDefined();
  expect(screen.getByText("The request wasn't valid.")).toBeDefined();
  expect(screen.getAllByText("Refused")).toHaveLength(2);
});
