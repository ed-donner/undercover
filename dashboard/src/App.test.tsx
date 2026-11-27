import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, mockApi, policy, summary } from "./testing";

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

it("moves between the queue, a claim and the instructions", async () => {
  mockApi({
    "/api/claims": [summary],
    "/api/claims/CLM-1001": claim,
    "/api/policies/POL-2001": policy,
    "/api/instructions": { text: "You are the UnderCover Agent." },
  });
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
  expect(screen.getByRole("link", { name: "Queue" }).ariaCurrent).toBe("page");

  go("#/claims/CLM-1001");
  expect(await screen.findByText(claim.story)).toBeDefined();

  go("#/instructions");
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Agent instructions" }).ariaCurrent,
  ).toBe("page");
});

it("shows an error when the instructions cannot load", async () => {
  mockApi({});
  window.location.hash = "#/instructions";
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "/api/instructions not found",
  );
});
