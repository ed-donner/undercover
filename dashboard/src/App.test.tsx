import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, mockApi, policy, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

const decided = {
  ...summary,
  claim_id: "CLM-1002",
  status: "decided",
  decision: "approve",
  payout: 1250,
};

it("shows the queue with counts by state", async () => {
  mockApi({ "/api/claims": [summary, decided] });
  render(<App />);
  expect(await screen.findByRole("link", { name: "CLM-1001" })).toBeDefined();
  const counts = screen.getByRole("region", { name: "Claims by state" });
  expect(within(counts).getByText("Waiting").previousSibling?.textContent).toBe(
    "1",
  );
  expect(screen.getByText("$1,250.00")).toBeDefined();
  expect(screen.getAllByText("Decided")).toHaveLength(2);
});

it("shows an error when the queue fails to load", async () => {
  mockApi({});
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain("404");
});

it("opens a claim in full", async () => {
  mockApi({
    "/api/claims/CLM-1001": claim,
    "/api/claims/CLM-1001/policy": policy,
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText(claim.story)).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(
    screen.getByText("The agent has not decided this claim yet."),
  ).toBeDefined();
});

it("shows the decision, reasons and payment", async () => {
  mockApi({
    "/api/claims/CLM-1001": {
      ...claim,
      status: "decided",
      decision: {
        decision: "approve",
        payout: 1500,
        reason: "The delay is covered.",
        policy_section: "Section 3, Trip Delay",
      },
      payment: { amount: 1500, signed_off_by: "Dana Whitfield" },
    },
    "/api/claims/CLM-1001/policy": policy,
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText("Decision: Approved")).toBeDefined();
  expect(screen.getByText("The delay is covered.")).toBeDefined();
  expect(screen.getByText("Section 3, Trip Delay")).toBeDefined();
  expect(screen.getByText(/signed off by Dana Whitfield/)).toBeDefined();
});

it("shows a decline without a payout", async () => {
  mockApi({
    "/api/claims/CLM-1001": {
      ...claim,
      status: "decided",
      decision: {
        decision: "decline",
        payout: 0,
        reason: "Not covered.",
        policy_section: "Section 9",
      },
    },
    "/api/claims/CLM-1001/policy": policy,
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText("Decision: Declined")).toBeDefined();
  expect(screen.queryByText(/Payout/)).toBeNull();
});

it("shows an unknown claim's error", async () => {
  mockApi({});
  window.location.hash = "#/claims/CLM-9999";
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain("CLM-9999");
});

it("shows the instructions read only", async () => {
  mockApi({ "/api/instructions": { text: "You are the UnderCover Agent." } });
  window.location.hash = "#/instructions";
  render(<App />);
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
});

it("shows an error when the instructions fail", async () => {
  mockApi({});
  window.location.hash = "#/instructions";
  render(<App />);
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("follows the hash as it changes", async () => {
  mockApi({
    "/api/claims": [summary],
    "/api/instructions": { text: "Instructions here" },
  });
  render(<App />);
  await screen.findByRole("link", { name: "CLM-1001" });
  act(() => {
    window.location.hash = "#/instructions";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  expect(await screen.findByText("Instructions here")).toBeDefined();
});
