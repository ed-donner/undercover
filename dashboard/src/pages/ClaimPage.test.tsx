import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { claimToWire, requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import type { Claim, Step } from "../types";
import { ClaimPage } from "./ClaimPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function makeClaim(overrides: Partial<Claim>): Claim {
  return {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled",
    story: "My flight home was canceled by the airline.",
    items: [
      {
        description: "Airport hotel",
        category: "accommodation",
        amount: 24500,
      },
    ],
    amount_claimed: 24500,
    documents: [],
    status: "waiting",
    decision: null,
    payout: null,
    reason: null,
    policy_reference: null,
    decided_on: null,
    over_approval_limit: null,
    signed_off_by: null,
    signed_off_on: null,
    paid_amount: null,
    paid_on: null,
    policy: {
      policy_id: "POL-2001",
      customer_id: "CUS-3001",
      plan: "premium",
      add_ons: [],
      purchased_on: "2026-04-22",
      sold_through: "Meridian Air checkout",
      trip: {
        destination: "Rome, Italy",
        departs_on: "2026-06-10",
        returns_on: "2026-06-18",
      },
      travelers: ["Maya Patel"],
      status: "active",
    },
    customer_previous_claims: [],
    ...overrides,
  };
}

function renderClaimPage() {
  render(
    <MemoryRouter initialEntries={["/claims/CLM-1001"]}>
      <Routes>
        <Route path="/claims/:claimId" element={<ClaimPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("shows a decided claim's story, items and decision", async () => {
  const claim = makeClaim({
    status: "decided",
    decision: "approve",
    payout: 24500,
    reason: "A covered trip delay with receipts.",
    policy_reference: "Section 3",
    customer_previous_claims: [
      {
        claim_id: "CLM-0412",
        filed_on: "2024-08-19",
        incident_date: "2024-08-09",
        claim_type: "baggage_delay",
        summary: "Checked bag arrived 30 hours late",
        outcome: "approved",
      },
    ],
  });
  const impl = (input: FetchInput): Promise<Response> => {
    const body = requestUrl(input).endsWith("/steps") ? [] : claimToWire(claim);
    return Promise.resolve(new Response(JSON.stringify(body)));
  };
  vi.stubGlobal("fetch", vi.fn(impl));

  renderClaimPage();

  expect(await screen.findByText(claim.story)).toBeDefined();
  expect(screen.getByText("Airport hotel: $245.00")).toBeDefined();
  expect(screen.getByText("approve, $245.00")).toBeDefined();
  expect(screen.getByText("A covered trip delay with receipts.")).toBeDefined();
  expect(screen.getByText(/Checked bag arrived 30 hours late/)).toBeDefined();
});

it("runs the agent and polls the step log as it works", async () => {
  const inProgress = makeClaim({ status: "in progress" });
  const stepLists: Step[][] = [
    [],
    [
      {
        recorded_on: "1",
        text: "Read the claim, its policy and the customer's claim history",
      },
    ],
    [
      {
        recorded_on: "1",
        text: "Read the claim, its policy and the customer's claim history",
      },
      { recorded_on: "2", text: "Decided: approve for $245.00" },
    ],
  ];
  let claimCalls = 0;
  let stepsCalls = 0;

  const impl = (input: FetchInput): Promise<Response> => {
    const url = requestUrl(input);
    if (url.endsWith("/run")) {
      return Promise.resolve(
        new Response(JSON.stringify(claimToWire(inProgress))),
      );
    }
    if (url.endsWith("/steps")) {
      const body = stepLists[Math.min(stepsCalls, stepLists.length - 1)];
      stepsCalls += 1;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }
    const body =
      claimCalls === 0 ? makeClaim({ status: "waiting" }) : inProgress;
    claimCalls += 1;
    return Promise.resolve(new Response(JSON.stringify(claimToWire(body))));
  };
  vi.stubGlobal("fetch", vi.fn(impl));

  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  renderClaimPage();
  const button = await screen.findByRole("button", { name: "Run agent" });

  fireEvent.click(button);
  await screen.findByText("in progress");

  vi.advanceTimersByTime(2000);
  expect(
    await screen.findByText(
      "Read the claim, its policy and the customer's claim history",
    ),
  ).toBeDefined();

  vi.advanceTimersByTime(2000);
  expect(await screen.findByText("Decided: approve for $245.00")).toBeDefined();
});
