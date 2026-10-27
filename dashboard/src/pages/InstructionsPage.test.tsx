import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./InstructionsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the agent's instructions", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ instructions: "Call decide_claim exactly once." }),
        ),
      ),
  );

  render(<InstructionsPage />);

  expect(
    await screen.findByText("Call decide_claim exactly once."),
  ).toBeDefined();
});
