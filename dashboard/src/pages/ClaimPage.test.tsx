import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "../types";
import { ClaimPage } from "./ClaimPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const claim: Claim = {
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
    { description: "Airport hotel", category: "accommodation", amount: 245 },
  ],
  amount_claimed: 245,
  documents: [],
  status: "decided",
  decision: "approve",
  payout: 245,
  reason: "A covered trip delay with receipts.",
  policy_reference: "Section 3",
  decided_on: "2026-06-26T00:00:00+00:00",
  over_approval_limit: 0,
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
      trip_cost: 3100,
    },
    travelers: ["Maya Patel"],
    status: "active",
  },
  customer_previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      incident_date: "2024-08-09",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

it("shows a claim's story, items and decision", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(claim))),
  );

  render(
    <MemoryRouter initialEntries={["/claims/CLM-1001"]}>
      <Routes>
        <Route path="/claims/:claimId" element={<ClaimPage />} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByText(claim.story)).toBeDefined();
  expect(screen.getByText("Airport hotel: $245.00")).toBeDefined();
  expect(screen.getByText("approve, $245.00")).toBeDefined();
  expect(screen.getByText("A covered trip delay with receipts.")).toBeDefined();
  expect(screen.getByText(/Checked bag arrived 30 hours late/)).toBeDefined();
});
