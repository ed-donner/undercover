import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const request = {
  request_id: "REQ-7001",
  type: "cancellation",
  created_at: "2026-11-06T08:35:00+05:30",
  customer_message: "Please cancel this order.",
  requested_scope: "whole_order",
  evidence: [],
};
const baseDetail = {
  request,
  customer: { customer_id: "CUS-001", name: "Asha Sharma" },
  order: {
    order_id: "ORD-2026-10001",
    placed_at: "2026-11-06T08:10:00+05:30",
    fulfillment_status: "confirmed",
    payment_status: "paid",
    payment_method: "upi",
    delivery_window: null,
    items: [
      {
        name: "Fruit box",
        sku: "FR-1",
        quantity: 1,
        unit_price: 349,
        line_total: 349,
      },
    ],
    subtotal: 349,
    delivery_fee: 0,
    total: 349,
  },
  status: "waiting",
  attempts: 0,
  recommendation: null,
  review: null,
  steps: [],
};
const queue = [
  {
    request_id: "REQ-7001",
    order_id: "ORD-2026-10001",
    customer_name: "Asha Sharma",
    type: "cancellation",
    created_at: "2026-11-06T08:35:00+05:30",
    status: "waiting",
    attempts: 0,
    recommendation: null,
    review: null,
  },
];
const instructions = {
  queue: "You are the Shoppie Agent, running the support queue.",
  request: "You are the Shoppie Agent, working one support request.",
};

function urlOf(input: RequestInfo | URL) {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function installFetch(
  detail: unknown = baseDetail,
  queueData: unknown[] = queue,
) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = urlOf(input);
    let body: unknown = detail;
    if (url === "/api/requests") body = queueData;
    if (url === "/api/agent/instructions") body = instructions;
    if (url === "/api/runs/current") body = null;
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

it("shows loading and empty queue states", async () => {
  let finish!: (value: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      if (urlOf(input) === "/api/requests") {
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      }
      if (urlOf(input) === "/api/runs/current")
        return Promise.resolve(new Response("null"));
      return Promise.resolve(new Response(JSON.stringify(instructions)));
    }),
  );
  render(<App />);
  expect(screen.getByText("Loading requests…")).toBeDefined();
  await waitFor(() => {
    expect(finish).toBeTypeOf("function");
  });
  finish(new Response("[]"));
  await waitFor(() => {
    expect(
      screen.getByText("There are no requests in the queue."),
    ).toBeDefined();
  });
});

it("shows a backend error for the queue", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "could not load the support queue",
  );
});

it("shows queue rows, selected request, order, and read-only instructions", async () => {
  installFetch();
  render(<App />);
  expect(await screen.findByRole("button", { name: /REQ-7001/ })).toBeDefined();
  expect(await screen.findByText("Please cancel this order.")).toBeDefined();
  expect(screen.getByText("Fruit box")).toBeDefined();
  expect(screen.getAllByText("₹349.00")).toHaveLength(3);
  fireEvent.click(screen.getByText("Shoppie Agent instructions"));
  expect(await screen.findByText(instructions.queue)).toBeDefined();
  expect(screen.getByText(instructions.request)).toBeDefined();
  expect(screen.getByText("Running the queue")).toBeDefined();
  expect(screen.getByText("Working a request")).toBeDefined();
  const instructionPanel = screen
    .getByText("Shoppie Agent instructions")
    .closest("details");
  expect(instructionPanel).not.toBeNull();
  expect(
    within(instructionPanel as HTMLElement).queryByRole("textbox"),
  ).toBeNull();
  expect(
    within(instructionPanel as HTMLElement).queryByRole("button"),
  ).toBeNull();
});

it("starts a capped run and shows the to-do list and decisions", async () => {
  const recommendation = {
    outcome: "approve",
    rationale: "The order has not been dispatched.",
    policy_citations: ["Cancellation Policy: before dispatch"],
    next_action: "Support agent to confirm the cancellation.",
    priority_human_review: false,
  };
  const completedDetail = {
    ...baseDetail,
    status: "waiting_for_agent_review",
    recommendation,
    steps: [
      {
        stage: "checking_policy",
        message: "The agent checked the applicable Shoppie policy.",
        created_at: "2026-11-06T09:00:00+05:30",
      },
    ],
  };
  const declined = {
    ...queue[0],
    request_id: "REQ-7002",
    status: "waiting_for_agent_review",
    recommendation: { ...recommendation, outcome: "decline" },
  };
  const finishedRun = {
    run_id: "RUN-1",
    cap: 2,
    status: "finished",
    started_at: "2026-11-06T09:00:00+05:30",
    finished_at: "2026-11-06T09:05:00+05:30",
    summary: "Two requests are waiting for support review.",
    todos: [
      {
        request_id: "REQ-7001",
        title: "REQ-7001 cancellation",
        status: "done",
      },
      { request_id: "REQ-7002", title: "REQ-7002 return", status: "done" },
    ],
  };
  let started = false;
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = urlOf(input);
    let body: unknown = started ? completedDetail : baseDetail;
    if (url === "/api/runs") {
      started = true;
      body = { run_id: "RUN-1", cap: 2, status: "running" };
    }
    if (url === "/api/runs/current") body = started ? finishedRun : null;
    if (url === "/api/requests")
      body = started
        ? [
            { ...queue[0], status: "waiting_for_agent_review", recommendation },
            declined,
          ]
        : [queue[0], { ...declined, status: "waiting", recommendation: null }];
    if (url === "/api/agent/instructions") body = instructions;
    return Promise.resolve(new Response(JSON.stringify(body)));
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  expect(screen.queryByRole("button", { name: /Ask agent/ })).toBeNull();
  const capInput = await screen.findByLabelText("Requests to work");
  expect(capInput).toHaveProperty("value", "2");
  fireEvent.change(capInput, { target: { value: "9" } });
  expect(capInput).toHaveProperty("value", "2");
  fireEvent.change(capInput, { target: { value: "0" } });
  expect(capInput).toHaveProperty("value", "1");
  fireEvent.change(capInput, { target: { value: "2" } });
  fireEvent.click(
    await screen.findByRole("button", { name: "Initiate processing" }),
  );
  expect(
    await screen.findByText("The order has not been dispatched."),
  ).toBeDefined();
  const queuePanel = screen.getByLabelText("Support request queue");
  expect(within(queuePanel).getByText("Approve")).toBeDefined();
  expect(within(queuePanel).getByText("Decline")).toBeDefined();
  expect(
    screen.getByText(/checked the applicable Shoppie policy/),
  ).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/runs",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ cap: 2 }),
    }),
  );
  const runPanel = screen.getByLabelText("Agent run");
  expect(within(runPanel).getByText("REQ-7001 cancellation")).toBeDefined();
  expect(within(runPanel).getAllByText("Done")).toHaveLength(2);
  expect(within(runPanel).getByText("Finished")).toBeDefined();
  expect(
    within(runPanel).getByText("Two requests are waiting for support review."),
  ).toBeDefined();
  expect(
    screen.getByText("Processing started for up to 2 waiting requests."),
  ).toBeDefined();
});

it("shows reviewed outcomes and failed runs in the queue", async () => {
  installFetch(baseDetail, [
    {
      ...queue[0],
      status: "decided",
      review: {
        outcome: "request_information",
        notes: "",
        reviewed_at: "2026-11-06T09:00:00+05:30",
      },
    },
    { ...queue[0], request_id: "REQ-7002", status: "waiting_for_agent_review" },
    { ...queue[0], request_id: "REQ-7003", status: "in_progress" },
  ]);
  render(<App />);
  const queuePanel = await screen.findByLabelText("Support request queue");
  expect(await within(queuePanel).findByText("Info requested")).toBeDefined();
  expect(within(queuePanel).getByText("Left for support")).toBeDefined();
  expect(within(queuePanel).getByText("In progress")).toBeDefined();
  expect(screen.getByRole("button", { name: "Processing…" })).toHaveProperty(
    "disabled",
    true,
  );
});

it("records a support reviewed outcome without a customer action", async () => {
  const reviewDetail = {
    ...baseDetail,
    status: "waiting_for_agent_review",
    recommendation: {
      outcome: "approve",
      rationale: "Within policy.",
      policy_citations: ["Cancellation Policy"],
      next_action: "Review the decision.",
      priority_human_review: false,
    },
  };
  const reviewed = {
    ...reviewDetail,
    status: "decided",
    review: {
      outcome: "approve",
      notes: "Reviewed.",
      reviewed_at: "2026-11-06T09:00:00+05:30",
    },
  };
  let detailCalls = 0;
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = urlOf(input);
    if (url.endsWith("/review")) return Promise.resolve(new Response("{}"));
    if (url === "/api/requests")
      return Promise.resolve(
        new Response(
          JSON.stringify([{ ...queue[0], status: "waiting_for_agent_review" }]),
        ),
      );
    if (url === "/api/agent/instructions")
      return Promise.resolve(new Response(JSON.stringify(instructions)));
    if (url === "/api/runs/current")
      return Promise.resolve(new Response("null"));
    detailCalls += 1;
    return Promise.resolve(
      new Response(JSON.stringify(detailCalls === 1 ? reviewDetail : reviewed)),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  fireEvent.change(await screen.findByLabelText("Reviewed outcome"), {
    target: { value: "decline" },
  });
  fireEvent.change(screen.getByLabelText(/Notes/), {
    target: { value: "Reviewed." },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Record support review" }),
  );
  expect(await screen.findByText("Review complete")).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/requests/REQ-7001/review",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ outcome: "decline", notes: "Reviewed." }),
    }),
  );
  expect(
    screen.getByText(/No customer or order action is performed here/),
  ).toBeDefined();
});

it("shows each to-do state while a run is going", async () => {
  const run = {
    run_id: "RUN-2",
    cap: 4,
    status: "running",
    started_at: "2026-11-06T09:00:00+05:30",
    finished_at: null,
    summary: null,
    todos: [
      { request_id: "REQ-7001", title: "First", status: "to_do" },
      { request_id: "REQ-7002", title: "Second", status: "in_progress" },
      { request_id: "REQ-7003", title: "Third", status: "done" },
      { request_id: "REQ-7004", title: "Fourth", status: "left_for_support" },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = urlOf(input);
      let body: unknown = baseDetail;
      if (url === "/api/requests") body = queue;
      if (url === "/api/agent/instructions") body = instructions;
      if (url === "/api/runs/current") body = run;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
  render(<App />);
  const runPanel = await screen.findByLabelText("Agent run");
  for (const label of ["To do", "In progress", "Done", "Left for support"])
    expect(within(runPanel).getByText(label)).toBeDefined();
  expect(within(runPanel).getByText("Running")).toBeDefined();
  expect(within(runPanel).getByText(/2 of 4 worked · cap 4/)).toBeDefined();
  expect(screen.getByRole("button", { name: "Processing…" })).toHaveProperty(
    "disabled",
    true,
  );
});

it("shows a stopped run that is still planning nothing", async () => {
  const run = {
    run_id: "RUN-3",
    cap: 1,
    status: "failed",
    started_at: "2026-11-06T09:00:00+05:30",
    finished_at: "2026-11-06T09:01:00+05:30",
    summary: "The run stopped: provider down",
    todos: [],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = urlOf(input);
      let body: unknown = baseDetail;
      if (url === "/api/requests") body = queue;
      if (url === "/api/agent/instructions") body = instructions;
      if (url === "/api/runs/current") body = run;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
  render(<App />);
  const runPanel = await screen.findByLabelText("Agent run");
  expect(within(runPanel).getByText("Stopped")).toBeDefined();
  expect(
    within(runPanel).getByText("The agent is planning its run."),
  ).toBeDefined();
  expect(
    within(runPanel).getByText("The run stopped: provider down"),
  ).toBeDefined();
});

it("says so when a run is already going", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === "/api/runs")
        return Promise.resolve(
          new Response(
            JSON.stringify({ detail: "A run is already in progress" }),
            { status: 409 },
          ),
        );
      let body: unknown = baseDetail;
      if (url === "/api/requests") body = queue;
      if (url === "/api/agent/instructions") body = instructions;
      if (url === "/api/runs/current") body = null;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Initiate processing" }),
  );
  expect(await screen.findByText("A run is already in progress")).toBeDefined();
});

it("shows the policy sections read and requests left for support", async () => {
  const detail = {
    ...baseDetail,
    status: "waiting_for_agent_review",
    attempts: 2,
    steps: [
      {
        stage: "read_section",
        message:
          "Read Shoppie Cancellation Policy, 2. Customer-requested cancellations.",
        created_at: "2026-11-06T09:00:00+05:30",
      },
      {
        stage: "read_section",
        message:
          "Read Shoppie Cancellation Policy, 2. Customer-requested cancellations.",
        created_at: "2026-11-06T09:00:00+05:30",
      },
      {
        stage: "left_for_support",
        message: "The agent could not complete its review after two attempts.",
        created_at: "2026-11-06T09:01:00+05:30",
      },
    ],
  };
  installFetch(detail, [
    { ...queue[0], status: "waiting_for_agent_review", attempts: 2 },
  ]);
  render(<App />);
  const queuePanel = await screen.findByLabelText("Support request queue");
  expect(await within(queuePanel).findByText("Left for support")).toBeDefined();
  expect(await screen.findByText("POLICY SECTIONS READ")).toBeDefined();
  expect(
    screen.getAllByText(
      "Shoppie Cancellation Policy, 2. Customer-requested cancellations",
    ),
  ).toHaveLength(1);
});
