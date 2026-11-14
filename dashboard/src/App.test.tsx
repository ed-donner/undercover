import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { date, label, money } from "./format";
import { fakeFetch, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

const CLAIMS = [
  summary(),
  summary({ claim_id: "CLM-1002", status: "decided", amount_claimed: 80 }),
  summary({ claim_id: "CLM-1003", status: "decided" }),
  summary({ claim_id: "CLM-1004", status: "awaiting_signoff" }),
];

function routes() {
  return fakeFetch({
    "GET /api/health": { status: "ok" },
    "GET /api/claims": CLAIMS,
    "GET /api/instructions": { instructions: "You are the UnderCover Agent." },
  });
}

it("shows that the backend is up", async () => {
  routes();
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("lists the queue with amounts, types and links", async () => {
  routes();
  render(<App />);
  const link = await screen.findByRole("link", { name: "CLM-1001" });
  expect(link.getAttribute("href")).toBe("#/claims/CLM-1001");
  expect(screen.getAllByRole("row")).toHaveLength(5);
  expect(screen.getAllByText("$1,250.00")).toHaveLength(3);
  expect(screen.getByText("$80.00")).toBeDefined();
  expect(screen.getAllByText("Trip delay")).toHaveLength(4);
});

it("counts the claims in each state", async () => {
  routes();
  render(<App />);
  expect((await screen.findByLabelText("Waiting count")).textContent).toBe("1");
  expect(screen.getByLabelText("In progress count").textContent).toBe("0");
  expect(screen.getByLabelText("Waiting for sign-off count").textContent).toBe(
    "1",
  );
  expect(screen.getByLabelText("Decided count").textContent).toBe("2");
});

it("colors each state chip", async () => {
  routes();
  render(<App />);
  await screen.findByRole("link", { name: "CLM-1001" });
  const chip = screen.getAllByText("Waiting for sign-off")[1];
  expect(chip.className).toBe("chip chip-awaiting_signoff");
});

it("shows an error when the queue fails", async () => {
  fakeFetch({ "GET /api/claims": new Response("{}", { status: 500 }) });
  render(<App />);
  expect(await screen.findByText("Could not load the queue.")).toBeDefined();
});

it("shows the instructions read only", async () => {
  routes();
  window.location.hash = "#/instructions";
  render(<App />);
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  const current = screen.getByRole("link", { current: "page" });
  expect(current.textContent).toBe("Instructions");
});

it("follows the hash to a claim", async () => {
  routes();
  render(<App />);
  await screen.findByRole("link", { name: "CLM-1001" });
  act(() => {
    window.location.hash = "#/claims/CLM-1001";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  expect(screen.getByRole("heading", { name: "CLM-1001" })).toBeDefined();
});

it("formats money, dates and labels", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(date("2026-06-24")).toBe("Jun 24, 2026");
  expect(date("2026-06-24T10:00:00+00:00")).toBe("Jun 24, 2026");
  expect(label("emergency_medical")).toBe("Emergency medical");
});
