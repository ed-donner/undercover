import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { queueEntry, stubApi } from "./testing";

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
