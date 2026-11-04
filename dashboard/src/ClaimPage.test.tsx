import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimPage } from "./ClaimPage";
import { claim, claimRoutes, customer, Failure, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const approved = claim({
  status: "decided",
  decision: "approve",
  payout: 420,
  reason: "The delay was caused by a crew problem. The costs are covered.",
  policy_section: "Section 3, Trip Delay",
  decided_at: "2026-11-04T17:16:40+00:00",
  paid_amount: 420,
  paid_at: "2026-11-04T17:16:44+00:00",
});

const held = claim({
  claim_id: "CLM-1003",
  status: "waiting_for_sign_off",
  decision: "approve",
  payout: 1500,
  reason: "The treatment is covered.",
  policy_section: "Section 7, Emergency Medical",
});

it("shows the claim, its policy and its customer in full", async () => {
  stubApi(claimRoutes(claim()));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByRole("heading", {
      name: "Flight home canceled by the airline",
    }),
  ).toBeDefined();
  const details = screen.getByRole("region", { name: "Claim" });
  expect(
    within(details).getByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(within(details).getByText("Jun 18, 2026, Rome, Italy")).toBeDefined();
  expect(
    within(details).getByRole("row", { name: "Total $420.00" }),
  ).toBeDefined();
  expect(within(details).getByText("Hotel receipt")).toBeDefined();
  const policy = screen.getByRole("region", { name: "Policy" });
  expect(await within(policy).findByText("UnderCover Premium")).toBeDefined();
  expect(within(policy).getByText("None")).toBeDefined();
  const person = screen.getByRole("region", { name: "Customer" });
  expect(await within(person).findByText("CLM-0412")).toBeDefined();
  expect(
    within(person).getByText(
      "Checked bag arrived 30 hours late in Lisbon. Approved, paid $140.00.",
    ),
  ).toBeDefined();
  expect(
    within(screen.getByRole("region", { name: "Decision" })).getByText(
      "The agent hasn't started on this claim.",
    ),
  ).toBeDefined();
});

it("says when a customer has no earlier claims", async () => {
  stubApi({
    ...claimRoutes(claim()),
    "GET /api/customers/CUS-3001": { ...customer, previous_claims: [] },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  const person = await screen.findByRole("region", { name: "Customer" });
  expect(await within(person).findByText("None.")).toBeDefined();
});

it("says when the agent is working on the claim", async () => {
  stubApi(claimRoutes(claim({ status: "in_progress" })));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent is working on this claim."),
  ).toBeDefined();
});

it("shows the decision, its reasons and the payment", async () => {
  stubApi(claimRoutes(approved));
  render(<ClaimPage claimId="CLM-1001" />);
  const decision = await screen.findByRole("region", { name: "Decision" });
  expect(within(decision).getByText("Approved")).toBeDefined();
  expect(within(decision).getByText("$420.00")).toBeDefined();
  expect(
    within(decision).getByText(
      "The delay was caused by a crew problem. The costs are covered.",
    ),
  ).toBeDefined();
  expect(
    within(decision).getByText("Policy wording: Section 3, Trip Delay"),
  ).toBeDefined();
  expect(within(decision).getByText(/^Paid \$420\.00 on Nov/)).toBeDefined();
});

it("shows an approval the agent hasn't paid yet", async () => {
  stubApi(
    claimRoutes({ ...approved, status: "in_progress", paid_amount: null }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Not paid yet.")).toBeDefined();
});

it.each([
  ["decline", "Declined", "Nothing to pay."],
  ["refer", "Referred", "A handler takes this claim from here."],
] as const)("shows a %s", async (decision, label, payment) => {
  stubApi(claimRoutes({ ...approved, decision, payout: 0, paid_amount: null }));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText(label)).toBeDefined();
  expect(screen.getByText(payment)).toBeDefined();
});

it("lets a handler sign off a payout over the limit, which pays it", async () => {
  const routes: Record<string, unknown> = {
    ...claimRoutes(held),
    "POST /api/claims/CLM-1003/sign-off": held,
  };
  const fetchStub = stubApi(routes);
  render(<ClaimPage claimId="CLM-1003" />);
  expect(
    await screen.findByText(
      "This payout waits for a handler's sign-off before it is paid.",
    ),
  ).toBeDefined();
  const button = screen.getByRole("button", {
    name: "Sign off and pay $1,500.00",
  });
  expect(button).toHaveProperty("disabled", true);
  const handler = screen.getByLabelText("Handler");
  expect(within(handler).queryByText("Priya Raman")).toBeNull();
  fireEvent.change(handler, { target: { value: "HND-01" } });
  routes["GET /api/claims/CLM-1003"] = {
    ...held,
    status: "decided",
    signed_off_by: "HND-01",
    signed_off_at: "2026-11-04T17:20:00+00:00",
    paid_amount: 1500,
    paid_at: "2026-11-04T17:20:00+00:00",
  };
  fireEvent.click(button);
  expect(
    await screen.findByText(/Signed off by Dana Whitfield\./),
  ).toBeDefined();
  expect(screen.getByText(/^Paid \$1,500\.00 on Nov/)).toBeDefined();
  expect(fetchStub).toHaveBeenCalledWith("/api/claims/CLM-1003/sign-off", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handler_id: "HND-01" }),
  });
});

it("shows why a sign-off didn't go through", async () => {
  stubApi({
    ...claimRoutes(held),
    "POST /api/claims/CLM-1003/sign-off": new Failure(
      409,
      "Claim CLM-1003 can't be signed off: it is decided.",
    ),
  });
  render(<ClaimPage claimId="CLM-1003" />);
  fireEvent.change(await screen.findByLabelText("Handler"), {
    target: { value: "HND-02" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Sign off and pay $1,500.00" }),
  );
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Claim CLM-1003 can't be signed off: it is decided.",
  );
});

it("says when a claim can't be loaded", async () => {
  stubApi({});
  render(<ClaimPage claimId="CLM-9999" />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Can't load claim CLM-9999.",
  );
});
