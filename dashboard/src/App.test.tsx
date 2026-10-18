import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { mockApi } from "./mockApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

it("shows that the backend is up and the queue", async () => {
  mockApi({ "GET /api/health": { status: "ok" }, "GET /api/claims": [] });
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("says when a page does not exist", () => {
  window.location.hash = "#/nowhere";
  mockApi({});
  render(<App />);
  expect(screen.getByText("Page not found.")).toBeDefined();
});
