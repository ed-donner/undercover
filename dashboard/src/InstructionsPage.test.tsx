import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./InstructionsPage";
import { stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows both sets of the agent's instructions, read only", async () => {
  stubApi({
    "GET /api/instructions": {
      queue: "You run the claims queue.",
      claim: "You decide one claim.",
    },
  });
  render(<InstructionsPage />);
  const queue = await screen.findByRole("region", {
    name: "Running the queue",
  });
  expect(queue.textContent).toContain("You run the claims queue.");
  expect(
    screen.getByRole("region", { name: "Working a claim" }).textContent,
  ).toContain("You decide one claim.");
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("says when the instructions can't be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<InstructionsPage />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Can't reach the claims system.",
  );
});
