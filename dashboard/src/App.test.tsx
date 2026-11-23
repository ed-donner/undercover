import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { detail, handlers, idle, steps, stubApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  window.location.hash = "";
  vi.unstubAllGlobals();
});

function serve() {
  stubApi({
    "GET /api/claims": [summary(1)],
    "GET /api/runs/current": idle,
    "GET /api/claims/CLM-1001": detail(),
    "GET /api/claims/CLM-1001/steps": steps,
    "GET /api/handlers": handlers,
    "GET /api/instructions": { text: "You are the agent." },
  });
}

it("shows the queue first", async () => {
  serve();
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
});

it("follows the address to a claim and the instructions", async () => {
  serve();
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText("Back to the queue")).toBeDefined();
  await act(async () => {
    window.location.hash = "#/instructions";
    await Promise.resolve();
  });
  expect(await screen.findByText("You are the agent.")).toBeDefined();
});
