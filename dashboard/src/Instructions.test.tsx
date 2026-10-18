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
    "GET /api/instructions": { text: "You are the UnderCover Agent." },
  });
  render(<Instructions />);
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
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
