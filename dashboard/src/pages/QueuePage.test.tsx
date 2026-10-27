import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import type { ClaimSummary } from "../types";
import { QueuePage } from "./QueuePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("lists claims with their status", async () => {
  const claims: ClaimSummary[] = [
    {
      claim_id: "CLM-1001",
      claim_type: "trip_delay",
      summary: "Flight home canceled",
      amount_claimed: 420,
      status: "waiting",
    },
    {
      claim_id: "CLM-1002",
      claim_type: "baggage",
      summary: "Lost bag",
      amount_claimed: 300,
      status: "decided",
    },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(claims))),
  );

  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("waiting")).toBeDefined();
  expect(screen.getByText("decided")).toBeDefined();
});
