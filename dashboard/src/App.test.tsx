import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, claimRoutes, queueEntry, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

function go(hash: string) {
  act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

it("opens on the queue", async () => {
  stubApi({ "GET /api/claims": [queueEntry()] });
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Queue" }).getAttribute("aria-current"),
  ).toBe("page");
});

it("says when a page doesn't exist, and goes back to the queue", async () => {
  stubApi({ "GET /api/claims": [queueEntry()] });
  render(<App />);
  go("#/nowhere");
  expect(screen.getByRole("heading", { name: "Page not found" })).toBeDefined();
  go("#/");
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
});

it("opens a claim and the agent's instructions", async () => {
  stubApi({
    ...claimRoutes(claim()),
    "GET /api/instructions": {
      queue: "You run the claims queue.",
      claim: "You are the UnderCover Agent.",
    },
  });
  render(<App />);
  go("#/claims/CLM-1001");
  expect(
    await screen.findByRole("heading", {
      name: "Flight home canceled by the airline",
    }),
  ).toBeDefined();
  go("#/instructions");
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
  expect(
    screen
      .getByRole("link", { name: "Agent instructions" })
      .getAttribute("aria-current"),
  ).toBe("page");
});
