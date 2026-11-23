import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Claim } from "./Claim";
import { detail, handlers, idle, Refusal, steps, stubApi } from "./testing";
import type { ClaimDetail } from "./api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function serve(claim: ClaimDetail, extra: Record<string, unknown> = {}) {
  return stubApi({
    "GET /api/claims/CLM-1001": claim,
    "GET /api/claims/CLM-1001/steps": steps,
    "GET /api/handlers": handlers,
    "GET /api/runs/current": idle,
    ...extra,
  });
}

const approved = {
  decision: "approve" as const,
  payout: 325,
  explanation: "The hotel and taxis are covered.",
  policy_section: "3. Trip Delay",
  decided_at: "2026-11-23T10:00:00+00:00",
};

it("shows the claim in full", async () => {
  serve(detail());
  render(<Claim claimId="CLM-1001" />);
  expect(
    await screen.findByText("My flight was canceled and I stayed a night."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("$325.00")).toBeDefined();
  expect(screen.getByText("Hotel Aurelia, $245.00")).toBeDefined();
  expect(
    screen.getByText(/UnderCover Premium, deductible \$50.00/),
  ).toBeDefined();
  expect(screen.getByText(/CLM-0412/)).toBeDefined();
  expect(screen.getByText("No decision yet.")).toBeDefined();
  expect(document.body.textContent).not.toContain("@");
});

it("shows the decision, the reasons and the policy section", async () => {
  serve(detail({ state: "decided", decision: approved }));
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText("Approved")).toBeDefined();
  expect(screen.getByText("The hotel and taxis are covered.")).toBeDefined();
  expect(screen.getByText("3. Trip Delay")).toBeDefined();
  expect(screen.getByText("Approved, not paid yet.")).toBeDefined();
});

it("shows a declined claim without a payout", async () => {
  const declined = { ...approved, decision: "decline" as const, payout: 0 };
  serve(detail({ state: "decided", decision: declined }));
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText("Declined")).toBeDefined();
  expect(screen.queryByText(/with a payout of/)).toBeNull();
  expect(screen.getByText("No payment.")).toBeDefined();
});

it("shows what the agent did, step by step", async () => {
  serve(detail());
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText("What the agent did")).toBeDefined();
  expect(
    screen.getByText('get_claim_context({"claim_id": "CLM-1001"})'),
  ).toBeDefined();
  expect(screen.getByText("Approved, $325.00.")).toBeDefined();
  expect(screen.getByText("Tool call")).toBeDefined();
});

it("says when the agent has not worked on the claim", async () => {
  serve(detail(), { "GET /api/claims/CLM-1001/steps": [] });
  render(<Claim claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent has not worked on this claim."),
  ).toBeDefined();
});

it("blocks a payout over the limit until a handler signs it off", async () => {
  const waiting = detail({
    state: "waiting for sign-off",
    decision: { ...approved, payout: 1500 },
  });
  const calls = serve(waiting, {
    "POST /api/claims/CLM-1001/sign-off": {
      amount: 1500,
      signed_off_by: "HND-02",
      paid_at: "2026-11-23T10:05:00+00:00",
    },
  });
  render(<Claim claimId="CLM-1001" />);
  expect(
    await screen.findByText(/blocked until a handler signs it off/),
  ).toBeDefined();
  const picker = screen.getByLabelText(/Signing off as/);
  expect(
    within(picker)
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["Dana Whitfield", "Marcus Oyelaran"]);
  fireEvent.change(picker, { target: { value: "HND-02" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  await waitFor(() => {
    expect(calls.some((call) => call.key.startsWith("POST"))).toBe(true);
  });
  const signOff = calls.find((call) => call.key.startsWith("POST"));
  expect(signOff?.key).toBe("POST /api/claims/CLM-1001/sign-off");
  expect(signOff?.body).toEqual({ handler_id: "HND-02" });
});

it("says why a sign-off was refused", async () => {
  serve(
    detail({
      state: "waiting for sign-off",
      decision: { ...approved, payout: 1500 },
    }),
    {
      "POST /api/claims/CLM-1001/sign-off": new Refusal(
        "Priya cannot sign off",
      ),
    },
  );
  render(<Claim claimId="CLM-1001" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Sign off and pay" }),
  );
  expect(await screen.findByText("Priya cannot sign off")).toBeDefined();
});

it("shows a payment that a handler signed off", async () => {
  serve(
    detail({
      state: "decided",
      decision: { ...approved, payout: 1500 },
      payment: {
        amount: 1500,
        signed_off_by: "HND-01",
        paid_at: "2026-11-23T10:05:00+00:00",
      },
    }),
  );
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText(/signed off by Dana Whitfield/)).toBeDefined();
  expect(screen.queryByRole("button", { name: "Sign off and pay" })).toBeNull();
});

it("shows a payment made without sign-off", async () => {
  serve(
    detail({
      state: "decided",
      decision: approved,
      payment: {
        amount: 325,
        signed_off_by: null,
        paid_at: "2026-11-23T10:05:00+00:00",
      },
    }),
  );
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText(/Paid/)).toBeDefined();
  expect(screen.queryByText(/signed off by/)).toBeNull();
});

it("runs the agent on a claim with no decision", async () => {
  const calls = serve(detail(), {
    "POST /api/claims/CLM-1001/run": { active: true, claim_id: "CLM-1001" },
  });
  render(<Claim claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run the agent" }));
  await waitFor(() => {
    expect(
      calls.some((call) => call.key === "POST /api/claims/CLM-1001/run"),
    ).toBe(true);
  });
});

it("cannot run the agent on a decided claim or during a run", async () => {
  serve(detail({ state: "decided", decision: approved }));
  render(<Claim claimId="CLM-1001" />);
  const button = await screen.findByRole("button", { name: "Run the agent" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  cleanup();
  serve(detail(), {
    "GET /api/runs/current": { active: true, claim_id: "CLM-1002" },
  });
  render(<Claim claimId="CLM-1001" />);
  const other = await screen.findByRole("button", { name: "Run the agent" });
  expect((other as HTMLButtonElement).disabled).toBe(true);
});

it("says why a run could not start", async () => {
  serve(detail(), {
    "POST /api/claims/CLM-1001/run": new Refusal("A run is already active"),
  });
  render(<Claim claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run the agent" }));
  expect(await screen.findByText("A run is already active")).toBeDefined();
});

it("says when the claim could not be loaded", async () => {
  stubApi({});
  render(<Claim claimId="CLM-0000" />);
  expect(
    await screen.findByText("No stub for GET /api/claims/CLM-0000"),
  ).toBeDefined();
});

it("shows a customer with no earlier claims", async () => {
  const base = detail();
  serve({
    ...base,
    customer: { ...base.customer, previous_claims: [] },
    policy: { ...base.policy, add_ons: [] },
  });
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText("No earlier claims.")).toBeDefined();
});
