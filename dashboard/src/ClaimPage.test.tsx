import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Decision } from "./api";
import { ClaimPage } from "./ClaimPage";
import { POLL_MS } from "./hooks";
import {
  calls,
  claim,
  Failure,
  handlers,
  mockApi,
  policy,
  Replies,
  step,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const approval: Decision = {
  decision: "approve",
  payout: 1250,
  reason: "The suitcase was lost by the airline. The items are covered.",
  policy_section: "Section 5, Baggage and Personal Effects",
  decided_at: "2026-10-28T10:00:00+00:00",
};

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/claims/CLM-1001": claim(),
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": policy,
    "GET /api/handlers": handlers,
    ...overrides,
  };
}

it("shows a waiting claim in full and runs the agent", async () => {
  const fetchMock = mockApi(
    routes({ "POST /api/claims/CLM-1001/run": { status: "in_progress" } }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel, one night")).toBeDefined();
  expect(screen.getByText("Hotel Aurelia. Total paid: $245.00.")).toBeDefined();
  expect(screen.getByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("Electronics Plus")).toBeDefined();
  expect(screen.getByText("No decision yet.")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Run agent" }));
  await vi.waitFor(() => {
    expect(calls(fetchMock)).toContain("POST /api/claims/CLM-1001/run");
  });
});

it("shows the agent's steps as they arrive", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockApi(
    routes({
      "GET /api/claims/CLM-1001": claim({ status: "in_progress" }),
      "GET /api/claims/CLM-1001/steps": new Replies([
        [step(1)],
        [step(1), step(2, { kind: "tool_result", text: "get_claim: {}" })],
      ]),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  const list = await screen.findByRole("list", { name: "Agent steps" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(1);
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  const items = within(list).getAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[1]?.textContent).toBe("Resultget_claim: {}");
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
});

it("shows a decided claim with its decision", async () => {
  mockApi(
    routes({
      "GET /api/claims/CLM-1001": claim({
        status: "decided",
        decision: {
          ...approval,
          decision: "decline",
          payout: 0,
          reason: "Lost through being left unattended.",
        },
      }),
      "GET /api/claims/CLM-1001/steps": [
        step(1, { kind: "reply", text: "Declined." }),
      ],
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Declined")).toBeDefined();
  expect(screen.getByText("$0.00")).toBeDefined();
  expect(screen.getByText("Lost through being left unattended.")).toBeDefined();
  expect(
    screen.getByText("Policy wording: Section 5, Baggage and Personal Effects"),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
  expect(screen.queryByRole("combobox")).toBeNull();
});

it("signs off a payout over the limit", async () => {
  const fetchMock = mockApi(
    routes({
      "GET /api/claims/CLM-1001": new Replies([
        claim({ status: "awaiting_sign_off", decision: approval }),
        claim({
          status: "decided",
          decision: approval,
          sign_off: { handler_id: "HND-01", signed_off_at: "2026-10-28" },
          payment: { amount: 1250, paid_at: "2026-10-28" },
        }),
      ]),
      "POST /api/claims/CLM-1001/sign-off": claim(),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("The payment waits for a handler's sign-off."),
  ).toBeDefined();
  const submit = screen.getByRole("button", { name: "Sign off and pay" });
  expect(submit.hasAttribute("disabled")).toBe(true);
  fireEvent.change(await screen.findByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(submit);
  expect(
    await screen.findByText("after sign-off by Dana Whitfield", {
      exact: false,
    }),
  ).toBeDefined();
  expect(calls(fetchMock)).toContain("POST /api/claims/CLM-1001/sign-off");
});

it("shows the backend's message when sign-off fails", async () => {
  mockApi(
    routes({
      "GET /api/claims/CLM-1001": claim({
        status: "awaiting_sign_off",
        decision: approval,
      }),
      "POST /api/claims/CLM-1001/sign-off": new Failure(
        409,
        "Claim CLM-1001 is not waiting for sign-off.",
      ),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Claim CLM-1001 is not waiting for sign-off.",
  );
});

it("shows an approval that has not been paid", async () => {
  mockApi(
    routes({
      "GET /api/claims/CLM-1001": claim({
        status: "decided",
        decision: { ...approval, payout: 420 },
      }),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Not paid yet.")).toBeDefined();
});

it("shows an error when the claim cannot load", async () => {
  mockApi(
    routes({
      "GET /api/claims/CLM-1001": new Failure(
        404,
        "There is no claim CLM-1001.",
      ),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "There is no claim CLM-1001.",
  );
});
