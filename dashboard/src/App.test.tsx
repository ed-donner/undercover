import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the nav and the queue by default", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]")));
  render(<App />);

  expect(screen.getByRole("link", { name: "Queue" })).toBeDefined();
  expect(screen.getByRole("link", { name: "Instructions" })).toBeDefined();
  await screen.findByRole("table");
});
