import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Claim, Step } from "./api";
import { ClaimView } from "./ClaimView";
import { section } from "./format";
import { claim, fakeFetch, type Routes } from "./testing";

const WORDING =
  "# Wording\n\n## 2. Trip Cancellation\n\nCancel text.\n\n## 3. Trip Delay\n\nWe pay when your carrier delays you.\n";

const POLICY = {
  policy_id: "POL-2001",
  plan: "premium",
  add_ons: ["electronics_plus"],
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  plan_details: { name: "UnderCover Premium", deductible: 50 },
  add_on_details: [
    { add_on: "electronics_plus", name: "Electronics Plus", effect: "" },
  ],
};

const HISTORY = {
  customer_id: "CUS-3001",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

const HANDLERS = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-02",
    name: "Sam Ortiz",
    role: "Handler",
    can_approve_over_limit: false,
  },
];

const DECIDED = {
  status: "decided",
  decision: "approve",
  payout: 420,
  reason: "The flight was canceled for a crew problem.",
  policy_section: "3. Trip Delay",
  decided_at: "2026-11-14T10:00:00+00:00",
} as const;

function step(content: string, kind: Step["kind"] = "tool_call"): Step {
  return { kind, content, created_at: "2026-11-14T10:00:00+00:00" };
}

function routes(current: () => Claim, steps: () => Step[], extra: Routes = {}) {
  return fakeFetch({
    "GET /api/claims/CLM-1001": current,
    "GET /api/claims/CLM-1001/steps": steps,
    "GET /api/policies/POL-2001": POLICY,
    "GET /api/customers/CUS-3001/history": HISTORY,
    "GET /api/policy-wording": { wording: WORDING },
    "GET /api/handlers": HANDLERS,
    ...extra,
  });
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const tick = () =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });

it("shows the claim in full", async () => {
  routes(
    () => claim(),
    () => [],
  );
  render(<ClaimView claimId="CLM-1001" />);
  expect(
    await screen.findByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("One night: $245.00.")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("Electronics Plus")).toBeDefined();
  expect(
    await screen.findByText("Checked bag arrived 30 hours late in Lisbon"),
  ).toBeDefined();
  expect(
    screen.getByText("The agent has not worked on this claim yet."),
  ).toBeDefined();
  expect(screen.queryByLabelText("Decision")).toBeNull();
});

it("runs the agent and shows its steps as they arrive", async () => {
  let current = claim();
  let steps: Step[] = [];
  const fetch = routes(
    () => current,
    () => steps,
    {
      "POST /api/claims/CLM-1001/run": () => {
        current = claim({ status: "in_progress" });
        return { status: "started" };
      },
    },
  );
  render(<ClaimView claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(await screen.findByText("In progress")).toBeDefined();
  expect(screen.getByText("The agent is working...")).toBeDefined();

  steps = [step('get_claim({"claim_id": "CLM-1001"})')];
  await tick();
  expect(screen.getByText('get_claim({"claim_id": "CLM-1001"})')).toBeDefined();

  steps = [...steps, step("Approved and paid.", "message")];
  current = claim({ ...DECIDED, paid_amount: 420, paid_at: "2026-11-14" });
  await tick();
  const list = within(screen.getByLabelText("Agent steps"));
  expect(list.getAllByRole("listitem")).toHaveLength(2);
  expect(screen.getByText("Decided")).toBeDefined();
  expect(screen.queryByText("The agent is working...")).toBeNull();

  const calls = fetch.mock.calls.length;
  await tick();
  await tick();
  expect(fetch.mock.calls).toHaveLength(calls);
});

it("picks up a run started elsewhere", async () => {
  let current = claim();
  let steps: Step[] = [];
  routes(
    () => current,
    () => steps,
  );
  render(<ClaimView claimId="CLM-1001" />);
  expect(await screen.findByText("Waiting")).toBeDefined();
  current = claim({ status: "in_progress" });
  steps = [step('get_claim({"claim_id": "CLM-1001"})')];
  await tick();
  expect(screen.getByText("In progress")).toBeDefined();
  expect(screen.getByText("The agent is working...")).toBeDefined();
  expect(screen.getByText('get_claim({"claim_id": "CLM-1001"})')).toBeDefined();
});

it("shows a decided claim's decision, section and payment", async () => {
  routes(
    () =>
      claim({
        ...DECIDED,
        paid_amount: 420,
        paid_at: "2026-11-14T10:00:00+00:00",
      }),
    () => [step("done", "message")],
  );
  render(<ClaimView claimId="CLM-1001" />);
  const panel = within(await screen.findByLabelText("Decision"));
  expect(panel.getByText(/^Approve/).textContent).toBe("Approve $420.00");
  expect(
    panel.getByText("The flight was canceled for a crew problem."),
  ).toBeDefined();
  expect(panel.getByText("3. Trip Delay")).toBeDefined();
  expect(panel.getByText(/Paid/).textContent).toBe(
    "Paid $420.00 on Nov 14, 2026.",
  );
  expect(
    await panel.findByText(/We pay when your carrier delays you/),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
});

it("shows an approval not yet paid, and a decline with no payout", async () => {
  let current = claim({ ...DECIDED });
  routes(
    () => current,
    () => [],
  );
  const { unmount } = render(<ClaimView claimId="CLM-1001" />);
  expect(await screen.findByText("Not paid yet.")).toBeDefined();
  unmount();
  current = claim({ ...DECIDED, decision: "decline", payout: 0 });
  render(<ClaimView claimId="CLM-1001" />);
  const panel = within(await screen.findByLabelText("Decision"));
  expect(panel.getByText("Decline")).toBeDefined();
  expect(panel.queryByText("$0.00")).toBeNull();
  expect(panel.queryByText("Not paid yet.")).toBeNull();
});

it("signs off a large payout and pays it", async () => {
  let current = claim({
    ...DECIDED,
    status: "awaiting_signoff",
    payout: 1150,
  });
  const fetch = routes(
    () => current,
    () => [],
    {
      "POST /api/claims/CLM-1001/signoff": () => {
        current = {
          ...current,
          status: "decided",
          signed_off_by: "HND-01",
          signed_off_at: "2026-11-14T11:00:00+00:00",
        };
        return current;
      },
      "POST /api/claims/CLM-1001/payment": () => {
        current = {
          ...current,
          paid_amount: 1150,
          paid_at: "2026-11-14T11:00:00+00:00",
        };
        return current;
      },
    },
  );
  render(<ClaimView claimId="CLM-1001" />);
  expect(
    await screen.findByText(/over the approval limit/, { exact: false }),
  ).toBeDefined();
  const select = screen.getByLabelText("Handler");
  await screen.findByRole("option", { name: "Dana Whitfield" });
  expect(screen.queryByRole("option", { name: "Sam Ortiz" })).toBeNull();
  const button = screen.getByRole("button", { name: "Sign off and pay" });
  expect(button.hasAttribute("disabled")).toBe(true);
  fireEvent.change(select, { target: { value: "HND-01" } });
  fireEvent.click(button);
  expect(
    await screen.findByText("Signed off by Dana Whitfield on Nov 14, 2026."),
  ).toBeDefined();
  expect(screen.getByText(/^Paid/).textContent).toBe(
    "Paid $1,150.00 on Nov 14, 2026.",
  );
  const payment = fetch.mock.calls.find(
    ([path]) => path === "/api/claims/CLM-1001/payment",
  );
  expect(payment?.[1]?.body).toBe(JSON.stringify({ amount: 1150 }));
});

it("shows the backend's refusal in plain English", async () => {
  routes(
    () => claim(),
    () => [],
    {
      "POST /api/claims/CLM-1001/run": Response.json(
        { detail: "CLM-1001 is in_progress, not waiting" },
        { status: 409 },
      ),
    },
  );
  render(<ClaimView claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "CLM-1001 is in_progress, not waiting",
  );
});

it("shows a claim that can't be found", async () => {
  fakeFetch({
    "GET /api/claims/CLM-0000": Response.json(
      { detail: "CLM-0000 was not found" },
      { status: 404 },
    ),
    "GET /api/claims/CLM-0000/steps": [],
  });
  render(<ClaimView claimId="CLM-0000" />);
  expect(await screen.findByText("CLM-0000 was not found")).toBeDefined();
});

it("finds a section of the wording by its number", () => {
  expect(section(WORDING, "Section 3, Trip Delay")).toBe(
    "## 3. Trip Delay\n\nWe pay when your carrier delays you.",
  );
  expect(section(WORDING, "Trip Delay")).toBeUndefined();
  expect(section(WORDING, "9. General exclusions")).toBeUndefined();
});
