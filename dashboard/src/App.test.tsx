import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claimRoutes, detail } from "./fixtures";
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

it("shows the instructions page", async () => {
  window.location.hash = "#/instructions";
  mockApi({
    "GET /api/health": { status: "ok" },
    "GET /api/instructions": { queue: "Be quick.", claim: "Be careful." },
  });
  render(<App />);
  expect(await screen.findByText("Be careful.")).toBeDefined();
});

it("shows a claim page", async () => {
  window.location.hash = "#/claims/CLM-1001";
  mockApi({ "GET /api/health": { status: "ok" }, ...claimRoutes(detail()) });
  render(<App />);
  expect(
    await screen.findByText("My flight home was canceled by the airline."),
  ).toBeDefined();
});
