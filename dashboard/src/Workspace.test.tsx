import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { approve, fixture } from "../test-fixtures";
import { ClaimWorkspace, Instructions } from "./ClaimWorkspace";
import { ActivityPanel, ClaimActions, DecisionPanel } from "./DecisionPanel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("starts a claim and refreshes server state", async () => {
  const data = fixture();
  const onChange = vi.fn();
  render(<ClaimWorkspace id="CLM-1001" onChange={onChange} />);
  fireEvent.click(await screen.findByRole("button", { name: /Process claim/ }));
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledOnce();
  });
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/agent-runs",
    expect.objectContaining({
      method: "POST",
      body: '{"mode":"claim","claim_id":"CLM-1001"}',
    }),
  );
});

it("signs off an above-limit approval, then separately records payment", async () => {
  const data = fixture();
  approve(data.claim, 1200);
  const onChange = vi.fn();
  const { rerender } = render(
    <ClaimActions
      claim={data.claim}
      handlers={data.handlers}
      runs={[]}
      onChange={onChange}
    />,
  );
  expect(
    screen.getByRole("button", { name: "Sign off payout" }),
  ).toHaveProperty("disabled", true);
  fireEvent.change(screen.getByLabelText("Signing handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off payout" }));
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledOnce();
  });
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/claims/CLM-1001/sign-off",
    expect.objectContaining({ body: '{"handler_id":"HND-01"}' }),
  );
  data.claim.status = "decided";
  rerender(
    <ClaimActions
      claim={data.claim}
      handlers={data.handlers}
      runs={[]}
      onChange={onChange}
    />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Record simulated payment" }),
  );
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledTimes(2);
  });
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/claims/CLM-1001/payment",
    expect.objectContaining({ body: '{"amount":1200}' }),
  );
});

it("shows backend rejection without pretending a claim was paid", async () => {
  const data = fixture();
  approve(data.claim);
  data.fetcher.mockResolvedValueOnce(
    Response.json(
      { detail: "Handler sign-off required before payment" },
      { status: 409 },
    ),
  );
  render(
    <>
      <ClaimActions
        claim={data.claim}
        handlers={data.handlers}
        runs={[]}
        onChange={vi.fn()}
      />
      <DecisionPanel claim={data.claim} />
    </>,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Record simulated payment" }),
  );
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Handler sign-off required before payment",
  );
  expect(screen.getByText("No simulated payment recorded.")).toBeDefined();
});

it.each(["decline", "refer"] as const)(
  "shows a %s decision with no payment action",
  (outcome) => {
    const data = fixture();
    approve(data.claim);
    if (!data.claim.decision) throw new Error("Missing fixture decision");
    data.claim.decision.outcome = outcome;
    data.claim.decision.payout = 0;
    render(
      <>
        <DecisionPanel claim={data.claim} />
        <ClaimActions
          claim={data.claim}
          handlers={data.handlers}
          runs={[]}
          onChange={vi.fn()}
        />
      </>,
    );
    expect(screen.getByText(outcome)).toBeDefined();
    expect(screen.getByText("$0.00")).toBeDefined();
    expect(screen.queryByRole("button", { name: /payment/ })).toBeNull();
  },
);

it("shows payment, calculation, references and sign-off attribution", () => {
  const data = fixture();
  approve(data.claim, 1200);
  data.claim.sign_off = {
    handler_id: "HND-01",
    signed_at: "2026-11-10T10:00:00Z",
  };
  data.claim.payment = { amount: 1200, paid_at: "2026-11-10T10:01:00Z" };
  render(<DecisionPanel claim={data.claim} />);
  expect(
    screen.getByText("Simulated payment recorded: $1,200.00"),
  ).toBeDefined();
  expect(screen.getByText("Eligible costs: $1200.")).toBeDefined();
  expect(screen.getByText(/Policy sections 3, 10/)).toBeDefined();
  expect(screen.getByText("HND-01")).toBeDefined();
});

it("offers retry only for an undecided failed claim and keeps failure history", async () => {
  const data = fixture();
  const runs = [
    { ...data.run, status: "failed" as const, error: "Model unavailable" },
  ];
  const events = [
    {
      sequence: 1,
      run_id: "run-1",
      kind: "run_failed",
      label: "Agent run failed",
      created_at: data.run.started_at,
    },
  ];
  const onChange = vi.fn();
  const { rerender } = render(
    <>
      <ClaimActions
        claim={data.claim}
        handlers={data.handlers}
        runs={runs}
        onChange={onChange}
      />
      <ActivityPanel runs={runs} events={events} />
    </>,
  );
  expect(screen.getByRole("alert")).toHaveProperty(
    "textContent",
    "Model unavailable",
  );
  expect(screen.getByText("Agent run failed")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: /Retry claim/ }));
  await waitFor(() => {
    expect(onChange).toHaveBeenCalledOnce();
  });
  approve(data.claim);
  rerender(
    <ClaimActions
      claim={data.claim}
      handlers={data.handlers}
      runs={runs}
      onChange={onChange}
    />,
  );
  expect(screen.queryByRole("button", { name: /Retry claim/ })).toBeNull();
});

it("polls progress and shows the running state", async () => {
  const data = fixture();
  data.claim.status = "in_progress";
  data.responses.set("/api/claims/CLM-1001/runs", [data.run]);
  vi.useFakeTimers();
  render(<ClaimWorkspace id="CLM-1001" onChange={vi.fn()} />);
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(screen.getByText("Agent working")).toBeDefined();
  data.responses.set("/api/claims/CLM-1001/events", [
    {
      sequence: 1,
      run_id: "run-1",
      kind: "context_read",
      label: "Context retrieved",
      created_at: data.run.started_at,
    },
  ]);
  await act(() => vi.advanceTimersByTimeAsync(1500));
  expect(screen.getByText("Context retrieved")).toBeDefined();
  expect(screen.getByText("Thread thread-1")).toBeDefined();
});

it("retries a failed detail request", async () => {
  const data = fixture();
  data.fetcher.mockRejectedValueOnce(new Error("Details unavailable"));
  render(<ClaimWorkspace id="CLM-1001" onChange={vi.fn()} />);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry details" }));
  expect(
    await screen.findByRole("heading", { name: "Maya Patel", level: 2 }),
  ).toBeDefined();
});

it("retries instructions and wording failures", async () => {
  const data = fixture();
  const failures = new Set([
    "/api/instructions/claim",
    "/api/instructions/queue",
    "/api/wording",
  ]);
  data.fetcher.mockImplementation((input) =>
    failures.delete(input)
      ? Promise.reject(new Error(`Instructions unavailable: ${input}`))
      : Promise.resolve(Response.json(data.responses.get(input))),
  );
  render(<Instructions />);
  await screen.findByText(
    /Instructions unavailable: \/api\/instructions\/claim/,
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry instructions" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Retry queue instructions" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry wording" }));
  expect(await screen.findByText(/Read the wording and manual/)).toBeDefined();
  expect(await screen.findByText(/Receipts are required/)).toBeDefined();
});

it("renders purchased add-ons", async () => {
  const data = fixture();
  data.policy.add_ons = ["electronics_plus"];
  render(<ClaimWorkspace id="CLM-1001" onChange={vi.fn()} />);
  expect(await screen.findByText("electronics plus")).toBeDefined();
});
