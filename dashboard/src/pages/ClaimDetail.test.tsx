import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimDetail } from "./ClaimDetail";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function claim(overrides: Record<string, unknown> = {}) {
  return {
    claim_id: "CLM-1003",
    policy_id: "POL-2003",
    customer_id: "CUS-3003",
    claim_type: "emergency_medical",
    submitted_on: "2026-06-10",
    incident_date: "2026-06-05",
    incident_location: "Lisbon, Portugal",
    summary: "Emergency room visit",
    story: "I needed emergency treatment while traveling.",
    items: [
      { description: "Hospital bill", category: "medical", amount: 3800 },
    ],
    amount_claimed: 3800,
    documents: [
      { name: "Hospital bill", type: "receipt", content: "Itemized bill." },
    ],
    status: "waiting_for_sign_off",
    decision: "approve",
    payout: 3750,
    reason: "A sudden injury during the covered trip.",
    reference: "Policy wording, section 7",
    signed_off_by: null,
    paid_amount: null,
    customer: {
      customer_id: "CUS-3003",
      name: "Aiko Tanaka",
      email: "aiko.tanaka@example.com",
      phone: "+1 206 555 0121",
      date_of_birth: "1991-07-25",
      address: {
        street: "1 Pine St",
        city: "Seattle",
        state: "WA",
        zip: "98122",
      },
      customer_since: "2026-05-04",
      previous_claims: [],
    },
    policy: {
      policy_id: "POL-2003",
      customer_id: "CUS-3003",
      plan: "premium",
      add_ons: [],
      purchased_on: "2026-05-04",
      sold_through: "TripNest checkout",
      trip: { destination: "Lisbon, Portugal" },
      travelers: ["Aiko Tanaka"],
      status: "active",
      plan_limits: {
        plan: "premium",
        name: "UnderCover Premium",
        trip_cancellation_max: 5000,
        trip_delay_waiting_hours: 6,
        trip_delay_max: 800,
        baggage_delay_waiting_hours: 12,
        baggage_delay_max: 300,
        baggage_max: 1500,
        per_item_limit: 300,
        passport_max: 250,
        emergency_medical_max: 100000,
        deductible: 50,
      },
    },
    ...overrides,
  };
}

const handlers = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    email: "",
    can_approve_over_limit: true,
  },
];

const events = [
  {
    operation_id: "decide_claim",
    message: "Decided to approve, payout $3,750.00",
    created_at: "2026-06-11T00:00:00Z",
  },
];

function stubFetch(claimBody: unknown) {
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/events"))
      return Promise.resolve(new Response(JSON.stringify(events)));
    if (url.endsWith("/handlers"))
      return Promise.resolve(new Response(JSON.stringify(handlers)));
    if (url.endsWith("/run"))
      return Promise.resolve(
        new Response(JSON.stringify({ reply: "Decided." })),
      );
    if (url.endsWith("/sign-off"))
      return Promise.resolve(
        new Response(JSON.stringify({ paid: true, status: "decided" })),
      );
    return Promise.resolve(new Response(JSON.stringify(claimBody)));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(claimId: string) {
  render(
    <MemoryRouter initialEntries={[`/claims/${claimId}`]}>
      <Routes>
        <Route element={<ClaimDetail />} path="/claims/:claimId" />
      </Routes>
    </MemoryRouter>,
  );
}

it("shows the claim, its decision and the sign-off control", async () => {
  stubFetch(claim());
  renderAt("CLM-1003");

  expect(await screen.findByText("CLM-1003")).toBeDefined();
  expect(screen.getByText(/needed emergency treatment/)).toBeDefined();
  expect(screen.getByText("Approved")).toBeDefined();
  expect(screen.getByText("Policy wording, section 7")).toBeDefined();
  expect(screen.getByRole("button", { name: "Sign off" })).toBeDefined();
  expect(
    screen.getByText("Decided to approve, payout $3,750.00"),
  ).toBeDefined();
});

it("offers to run a waiting claim instead", async () => {
  const fetchMock = stubFetch(
    claim({
      status: "waiting",
      decision: null,
      payout: null,
      reason: null,
      reference: null,
    }),
  );
  renderAt("CLM-1003");

  const button = await screen.findByRole("button", { name: "Run" });
  expect(screen.queryByRole("button", { name: "Sign off" })).toBeNull();

  fireEvent.click(button);
  expect(await screen.findByRole("button", { name: "Run" })).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/claims/CLM-1003/run",
    expect.objectContaining({ method: "POST" }),
  );
});

it("signs off a claim that is waiting for sign-off", async () => {
  const fetchMock = stubFetch(claim());
  renderAt("CLM-1003");

  const button = await screen.findByRole("button", { name: "Sign off" });
  fireEvent.click(button);

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/claims/CLM-1003/sign-off",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ handler_id: "HND-01" }),
    }),
  );
});

it("shows a declined decision and the customer's claim history", async () => {
  stubFetch(
    claim({
      status: "decided",
      decision: "decline",
      payout: 0,
      reason: "Not covered.",
      reference: "Policy wording, section 9",
      customer: {
        ...claim().customer,
        previous_claims: [
          {
            claim_id: "CLM-0412",
            filed_on: "2024-08-19",
            incident_date: "2024-08-09",
            claim_type: "baggage_delay",
            summary: "Checked bag arrived late",
            outcome: "approved",
            amount_paid: 140,
          },
        ],
      },
    }),
  );
  renderAt("CLM-1003");

  expect(await screen.findByText("Declined")).toBeDefined();
  expect(screen.getByText(/Checked bag arrived late/)).toBeDefined();
});
