import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimView } from "./ClaimView";
import { claimRoutes, detail, step } from "./fixtures";
import { mockApi } from "./mockApi";
import type { Decision } from "./types";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const decision = (overrides: Partial<Decision> = {}): Decision => ({
  decision: "approve",
  payout: 200,
  explanation: "The cancellation is covered.",
  policy_section: "Section 3, Trip Delay",
  decided_at: "2026-10-18T09:00:00+00:00",
  ...overrides,
});

const paid = { amount: 200, paid_at: "2026-10-18T09:00:00+00:00" };
const SIGN_OFF_ID = "HND-01";

it("shows the claim, its policy and the customer's history", async () => {
  mockApi(claimRoutes(detail()));
  render(<ClaimView id="CLM-1001" />);
  expect(
    await screen.findByText("My flight home was canceled by the airline."),
  ).toBeDefined();
  expect(screen.getByText("Waiting")).toBeDefined();
  expect(screen.getByText("June 18, 2026, Rome, Italy")).toBeDefined();
  expect(screen.getByText(/Airport hotel/)).toBeDefined();
  expect(screen.getByText(/Hotel receipt/)).toBeDefined();
  expect(await screen.findByText("Electronics Plus")).toBeDefined();
  expect(screen.getByText("Premium")).toBeDefined();
  expect(
    await screen.findByText(/Checked bag arrived 30 hours late/),
  ).toBeDefined();
  expect(screen.getByText("No steps yet.")).toBeDefined();
  expect(screen.queryByText("Sign-off needed")).toBeNull();
});

it("shows a paid decision with its reasons", async () => {
  const claim = detail({
    status: "decided",
    decision: decision(),
    payment: paid,
  });
  mockApi(
    claimRoutes(claim, [
      step(1, "tool_call", "get_claim({})"),
      step(2, "message", "Done"),
    ]),
  );
  render(<ClaimView id="CLM-1001" />);
  expect(
    await screen.findByRole("heading", { name: "Approved, $200.00" }),
  ).toBeDefined();
  expect(screen.getByText("The cancellation is covered.")).toBeDefined();
  expect(screen.getByText("Section 3, Trip Delay")).toBeDefined();
  expect(screen.getByText("Paid $200.00 on October 18, 2026.")).toBeDefined();
  expect(screen.getByText("get_claim({})")).toBeDefined();
  expect(screen.getByText("Tool call")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
});

it("says what a decline and an unpaid approval mean for payment", async () => {
  const claim = detail({
    status: "decided",
    decision: decision({ decision: "decline", payout: 0 }),
  });
  mockApi(claimRoutes(claim));
  const { unmount } = render(<ClaimView id="CLM-1001" />);
  expect(
    await screen.findByRole("heading", { name: "Declined" }),
  ).toBeDefined();
  expect(screen.getByText("Nothing to pay.")).toBeDefined();
  unmount();
  mockApi(claimRoutes(detail({ status: "decided", decision: decision() })));
  render(<ClaimView id="CLM-1001" />);
  expect(await screen.findByText("No payment has been made.")).toBeDefined();
});

it("lists what the agent read", async () => {
  const claim = detail({ status: "in_progress" });
  mockApi(
    claimRoutes(claim, [
      step(1, "tool_call", "read_section({'document': 'manual'})"),
      step(2, "read", "Claims manual, 9. Repeat claims"),
    ]),
  );
  render(<ClaimView id="CLM-1001" />);
  expect(await screen.findByText("What the agent read")).toBeDefined();
  expect(screen.getAllByText("Claims manual, 9. Repeat claims")).toHaveLength(
    2,
  );
  expect(screen.getByText("Read")).toBeDefined();
});

it("shows no read panel when the agent read nothing", async () => {
  mockApi(claimRoutes(detail()));
  render(<ClaimView id="CLM-1001" />);
  await screen.findByText("No steps yet.");
  expect(screen.queryByText("What the agent read")).toBeNull();
});

it("says when a claim needs a handler", async () => {
  mockApi(
    claimRoutes(detail({ status: "needs_handler" }), [
      step(1, "error", "Failed 2 times: left for a handler."),
    ]),
  );
  render(<ClaimView id="CLM-1001" />);
  expect(await screen.findByText(/A handler needs to work it/)).toBeDefined();
  expect(screen.getAllByText("Needs a handler")).toHaveLength(2);
});

it("runs the agent on a waiting claim", async () => {
  const fetchMock = mockApi({
    ...claimRoutes(detail()),
    "POST /api/claims/CLM-1001/run": {},
  });
  render(<ClaimView id="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(fetchMock).toHaveBeenCalledWith("/api/claims/CLM-1001/run", {
    method: "POST",
  });
});

it("tells the handler when the agent could not be started", async () => {
  mockApi(claimRoutes(detail()));
  render(<ClaimView id="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The agent could not be started.",
  );
});

it("holds a large payout for sign-off and releases it", async () => {
  let claim = detail({
    status: "waiting_for_sign_off",
    decision: decision({ payout: 1250 }),
  });
  const fetchMock = mockApi({
    ...claimRoutes(claim),
    "GET /api/claims/CLM-1001": () => claim,
    "POST /api/claims/CLM-1001/sign-off": () => {
      claim = {
        ...claim,
        status: "decided",
        payment: { amount: 1250, paid_at: "2026-10-18T09:00:00+00:00" },
        sign_off: {
          handler_id: SIGN_OFF_ID,
          handler_name: "Dana Whitfield",
          signed_at: "2026-10-18T09:00:00+00:00",
        },
      };
      return claim;
    },
  });
  render(<ClaimView id="CLM-1001" />);
  expect(await screen.findByText("Sign-off needed")).toBeDefined();
  expect(
    screen.getByText("The payment is held until a handler signs off."),
  ).toBeDefined();
  const select = screen.getByLabelText("Handler");
  expect(await within(select).findByText("Marcus Oyelaran")).toBeDefined();
  fireEvent.click(
    screen.getByRole("button", { name: "Sign off and pay $1,250.00" }),
  );
  expect(
    await screen.findByText("Dana Whitfield, October 18, 2026"),
  ).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith("/api/claims/CLM-1001/sign-off", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ handler_id: SIGN_OFF_ID }),
  });
  expect(screen.getByText("Paid $1,250.00 on October 18, 2026.")).toBeDefined();
  expect(screen.queryByText("Sign-off needed")).toBeNull();
});

it("signs off as the handler chosen", async () => {
  const claim = detail({
    status: "waiting_for_sign_off",
    decision: decision({ payout: 1250 }),
  });
  const fetchMock = mockApi({
    ...claimRoutes(claim),
    "POST /api/claims/CLM-1001/sign-off": claim,
  });
  render(<ClaimView id="CLM-1001" />);
  const select = await screen.findByLabelText("Handler");
  await within(select).findByText("Marcus Oyelaran");
  fireEvent.change(select, { target: { value: "HND-02" } });
  fireEvent.click(screen.getByRole("button", { name: /Sign off and pay/ }));
  const call = fetchMock.mock.calls.find(([path]) =>
    path.endsWith("/sign-off"),
  );
  expect(call?.[1]?.body).toBe(JSON.stringify({ handler_id: "HND-02" }));
});

it("tells the handler when a sign-off fails", async () => {
  mockApi(
    claimRoutes(
      detail({
        status: "waiting_for_sign_off",
        decision: decision({ payout: 1250 }),
      }),
    ),
  );
  render(<ClaimView id="CLM-1001" />);
  const select = await screen.findByLabelText("Handler");
  await within(select).findByText("Marcus Oyelaran");
  fireEvent.click(screen.getByRole("button", { name: /Sign off and pay/ }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "The sign-off did not go through.",
  );
});

it("keeps polling while the agent works and stops once it is done", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let steps = [step(1, "tool_call", "get_claim({})")];
  let claim = detail({ status: "in_progress" });
  const fetchMock = mockApi({
    ...claimRoutes(claim),
    "GET /api/claims/CLM-1001": () => claim,
    "GET /api/claims/CLM-1001/steps": () => steps,
  });
  render(<ClaimView id="CLM-1001" />);
  await screen.findByText("get_claim({})");
  expect(screen.getByText("In progress")).toBeDefined();
  claim = detail({ status: "decided", decision: decision(), payment: paid });
  steps = [...steps, step(2, "tool_result", "pay_claim: {}")];
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(await screen.findByText("pay_claim: {}")).toBeDefined();
  steps = [...steps, step(3, "message", "Approved $200.00.")];
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(await screen.findByText("Approved $200.00.")).toBeDefined();
  const calls = fetchMock.mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(fetchMock.mock.calls).toHaveLength(calls);
});

it("shows an error when the claim cannot be loaded", async () => {
  mockApi({});
  render(<ClaimView id="CLM-9999" />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "This claim could not be loaded.",
  );
});
