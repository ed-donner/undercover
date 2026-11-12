import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import { InstructionsPage } from "./InstructionsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the queue and claim instructions", async () => {
  const impl = (input: FetchInput): Promise<Response> => {
    const text = requestUrl(input).includes("queue-instructions")
      ? "Call work_claim once per claim."
      : "Call decide_claim exactly once.";
    return Promise.resolve(
      new Response(JSON.stringify({ instructions: text })),
    );
  };
  vi.stubGlobal("fetch", vi.fn(impl));

  render(<InstructionsPage />);

  expect(
    await screen.findByText("Call work_claim once per claim."),
  ).toBeDefined();
  expect(screen.getByText("Call decide_claim exactly once.")).toBeDefined();
});
