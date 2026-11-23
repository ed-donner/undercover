import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Instructions } from "./Instructions";
import { stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions and cannot change them", async () => {
  stubApi({
    "GET /api/instructions": {
      text: "You are the agent.\n\n## How to work\n\n1. Read the claim.\n2. Decide.",
    },
  });
  render(<Instructions />);
  expect(await screen.findByText("You are the agent.")).toBeDefined();
  expect(screen.getByRole("heading", { name: "How to work" })).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("says when the instructions could not be loaded", async () => {
  stubApi({});
  render(<Instructions />);
  expect(
    await screen.findByText("No stub for GET /api/instructions"),
  ).toBeDefined();
});
