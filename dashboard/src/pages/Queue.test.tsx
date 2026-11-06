import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { Queue } from "./Queue";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const claims = [
  {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    submitted_on: "2026-06-24",
    amount_claimed: 420,
    status: "waiting",
    decision: null,
    payout: null,
  },
  {
    claim_id: "CLM-1002",
    claim_type: "baggage",
    summary: "Suitcase lost",
    submitted_on: "2026-07-20",
    amount_claimed: 1150,
    status: "decided",
    decision: "approve",
    payout: 580,
  },
];

function stubFetch() {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST")
      return Promise.resolve(
        new Response(JSON.stringify({ reply: "Decided." })),
      );
    return Promise.resolve(new Response(JSON.stringify(claims)));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

it("lists the claims in the queue", async () => {
  stubFetch();
  render(
    <MemoryRouter>
      <Queue />
    </MemoryRouter>,
  );

  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("Waiting")).toBeDefined();
  expect(screen.getByText("Decided")).toBeDefined();
  expect(screen.getByText("Approved")).toBeDefined();
});

it("only offers to run a waiting claim", async () => {
  stubFetch();
  render(
    <MemoryRouter>
      <Queue />
    </MemoryRouter>,
  );

  await screen.findByText("CLM-1001");
  expect(screen.getAllByRole("button", { name: "Run" })).toHaveLength(1);
});

it("runs a claim when Run is clicked", async () => {
  const fetchMock = stubFetch();
  render(
    <MemoryRouter>
      <Queue />
    </MemoryRouter>,
  );

  const button = await screen.findByRole("button", { name: "Run" });
  fireEvent.click(button);

  expect(await screen.findByRole("button", { name: "Run" })).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/claims/CLM-1001/run",
    expect.objectContaining({ method: "POST" }),
  );
});
