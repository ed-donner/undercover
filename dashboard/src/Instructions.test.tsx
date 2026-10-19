import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Instructions } from "./Instructions";
import { mockApi } from "./mockApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the agent's instructions read only", async () => {
  mockApi({
    "GET /api/instructions": {
      queue: "You run the queue.",
      claim: "You work one claim.",
    },
  });
  render(<Instructions />);
  expect(await screen.findByText("You run the queue.")).toBeDefined();
  expect(screen.getByText("You work one claim.")).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("shows an error when the instructions cannot be loaded", async () => {
  mockApi({});
  render(<Instructions />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The instructions could not be loaded.",
  );
});
