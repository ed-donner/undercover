import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Step } from "./api";
import { Steps } from "./Steps";
import { sections, stubApi } from "./testing";

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

function stepOf(
  threadId: string,
  kind: Step["kind"],
  name: string,
  content: string,
) {
  return { ...step(kind, name, content), thread_id: threadId };
}

it("shows what the agent looked up and lists the sections it read", async () => {
  stubApi({
    "GET /api/documents/sections": sections,
    "GET /api/claims/CLM-1001/steps": [
      step("tool_call", "list_sections", "{}"),
      step("tool_call", "search_documents", '{"query": "repeat claims"}'),
      step(
        "tool_call",
        "read_section",
        '{"document": "claims_manual", "section": 9}',
      ),
      step(
        "tool_call",
        "read_section",
        '{"document": "claims_manual", "section": 9}',
      ),
      step(
        "tool_call",
        "read_section",
        '{"document": "policy_wording", "section": 12}',
      ),
    ],
  });
  render(<Steps claimId="CLM-1001" />);
  const read = await screen.findByRole("region", {
    name: "What the agent read",
  });
  expect(
    await within(read).findByText("Claims manual, section 9: Repeat claims"),
  ).toBeDefined();
  expect(
    within(read)
      .getAllByRole("listitem")
      .map((item) => item.textContent),
  ).toEqual([
    "Claims manual, section 9: Repeat claims",
    "Policy wording, section 12",
  ]);
  expect(
    screen.getByText("Reading the contents of the wording and the manual"),
  ).toBeDefined();
  expect(
    screen.getByText('Searching the documents for "repeat claims"'),
  ).toBeDefined();
  expect(
    screen.getAllByText("Reading Claims manual, section 9: Repeat claims"),
  ).toHaveLength(2);
});

it("leaves out what the agent read when it read no section", async () => {
  stubApi({
    "GET /api/claims/CLM-1001/steps": [
      step("tool_call", "read_section", "{}"),
      step("reply", "agent", "Done."),
    ],
  });
  render(<Steps claimId="CLM-1001" />);
  expect(await screen.findByText("Done.")).toBeDefined();
  expect(
    screen.queryByRole("region", { name: "What the agent read" }),
  ).toBeNull();
});

it("marks reminders and failures, and where each attempt starts", async () => {
  stubApi({
    "GET /api/claims/CLM-1002/steps": [
      stepOf("first", "reply", "agent", "Done."),
      stepOf(
        "first",
        "reminder",
        "harness",
        "You haven't recorded a decision.",
      ),
      stepOf("first", "failure", "harness", "This attempt failed: it stopped."),
      stepOf("second", "reply", "agent", "Declined."),
    ],
  });
  render(<Steps claimId="CLM-1002" />);
  expect(await screen.findByText("Reminder")).toBeDefined();
  expect(screen.getByText("Failed").className).toBe("badge step-failure");
  expect(screen.getByText("This attempt failed: it stopped.")).toBeDefined();
  expect(
    screen
      .getAllByRole("heading", { name: /^Attempt/ })
      .map((h) => h.textContent),
  ).toEqual(["Attempt 1", "Attempt 2"]);
});

it("doesn't number a claim's only attempt", async () => {
  stubApi({
    "GET /api/claims/CLM-1001/steps": [step("reply", "agent", "Declined.")],
  });
  render(<Steps claimId="CLM-1001" />);
  expect(await screen.findByText("Declined.")).toBeDefined();
  expect(screen.queryByRole("heading", { name: /^Attempt/ })).toBeNull();
});
