import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, run, stubApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

const routes = {
  "/api/health": { status: "ok" },
  "/api/claims": [summary],
  "/api/runs/current": run,
  "/api/claims/CLM-1001": claim,
  "/api/instructions": { queue: "Queue rules", claim: "Claim rules" },
};

it("shows that the backend is up", async () => {
  stubApi(routes);
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("shows the queue with the run's to-do list", async () => {
  stubApi(routes);
  render(<App />);
  expect(await screen.findByText("Flight canceled")).toBeDefined();
  const todos = await screen.findByRole("list", { name: "To-do list" });
  expect(todos.textContent).toContain("CLM-1002");
  expect(todos.textContent).toContain("In progress");
  expect(screen.getByText("Approved one claim.")).toBeDefined();
});

it("says so before any run", async () => {
  stubApi({ ...routes, "/api/runs/current": null });
  render(<App />);
  expect(await screen.findByText("No run yet.")).toBeDefined();
});

it("shows a claim with its steps and the sections the agent read", async () => {
  stubApi(routes);
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  const reads = await screen.findByRole("list", { name: "Sections read" });
  expect(reads.textContent).toContain("claims_manual section 9");
  expect(screen.getByRole("list", { name: "Steps" }).textContent).toContain(
    "Started in run 1",
  );
  expect(screen.getByText("Covered delay.")).toBeDefined();
});

it("shows the instructions", async () => {
  stubApi(routes);
  window.location.hash = "#/instructions";
  render(<App />);
  expect(await screen.findByText("Queue rules")).toBeDefined();
  expect(screen.getByText("Claim rules")).toBeDefined();
});
