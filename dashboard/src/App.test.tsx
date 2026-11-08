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
    recommendation: null,
    review: null,
  },
];
const instructions = "You are the Shoppie Agent. Use provided policies.";

function urlOf(input: RequestInfo | URL) {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function installFetch(detail = baseDetail, queueData: unknown[] = queue) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = urlOf(input);
    let body: unknown = detail;
    if (url === "/api/requests") body = queueData;
    if (url === "/api/agent/instructions") body = { instructions };
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
      return Promise.resolve(new Response(JSON.stringify({ instructions })));
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
  expect(await screen.findByText(instructions)).toBeDefined();
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

it("initiates processing for every request and shows decisions in the queue", async () => {
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
  let started = false;
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = urlOf(input);
    let body: unknown = started ? completedDetail : baseDetail;
    if (url === "/api/requests/run") {
      started = true;
      body = { request_ids: ["REQ-7001", "REQ-7002"] };
    }
    if (url === "/api/requests")
      body = started
        ? [
            { ...queue[0], status: "waiting_for_agent_review", recommendation },
            declined,
          ]
        : [queue[0], { ...declined, status: "waiting", recommendation: null }];
    if (url === "/api/agent/instructions") body = { instructions };
    return Promise.resolve(new Response(JSON.stringify(body)));
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  expect(screen.queryByRole("button", { name: /Ask agent/ })).toBeNull();
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
    "/api/requests/run",
    expect.objectContaining({ method: "POST" }),
  );
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
  expect(within(queuePanel).getByText("Needs review")).toBeDefined();
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
      return Promise.resolve(new Response(JSON.stringify({ instructions })));
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
