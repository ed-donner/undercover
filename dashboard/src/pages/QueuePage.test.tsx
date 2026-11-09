import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { requestUrl, summaryToWire } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import type { ClaimSummary, Run } from "../types";
import { QueuePage } from "./QueuePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const claims: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    amount_claimed: 42000,
    status: "waiting",
  },
  {
    claim_id: "CLM-1002",
    claim_type: "baggage",
    summary: "Lost bag",
    amount_claimed: 30000,
    status: "decided",
  },
];

function stubFetch(run: Run | null) {
  const impl = (input: FetchInput): Promise<Response> => {
    if (requestUrl(input).endsWith("/runs/current")) {
      return Promise.resolve(
        run ? new Response(JSON.stringify(run)) : new Response("null"),
      );
    }
    return Promise.resolve(
      new Response(JSON.stringify(claims.map(summaryToWire))),
    );
  };
  vi.stubGlobal("fetch", vi.fn(impl));
}

it("lists claims with their status", async () => {
  stubFetch(null);

  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("waiting")).toBeDefined();
  expect(screen.getByText("Waiting").nextElementSibling?.textContent).toBe("1");
  expect(screen.getByText("Decided").nextElementSibling?.textContent).toBe("1");
  expect(screen.getByText("decided")).toBeDefined();
  expect(screen.queryByText("The current run")).toBeNull();
});

it("shows the current run's to-do list", async () => {
  stubFetch({
    run_id: 1,
    started_on: "2026-01-01T00:00:00Z",
    finished_on: null,
    summary: null,
    items: [
      { claim_id: "CLM-1001", status: "in progress", attempts: 1, note: "" },
      {
        claim_id: "CLM-1002",
        status: "left for a handler",
        attempts: 2,
        note: "boom",
      },
    ],
  });

  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("The current run")).toBeDefined();
  expect(screen.getByText("in progress")).toBeDefined();
  expect(screen.getByText("left for a handler")).toBeDefined();
  expect(screen.getByText(/boom/)).toBeDefined();

  const left = screen.getByText("Left for a handler").nextElementSibling;
  expect(left?.textContent).toBe("1");
  const inProgress = screen.getByText("In progress").nextElementSibling;
  expect(inProgress?.textContent).toBe("0");
});
