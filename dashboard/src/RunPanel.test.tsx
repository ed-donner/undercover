import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import { RunPanel } from "./RunPanel";
import { fakeFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const run = (overrides: Partial<Run> = {}): Run => ({
  id: 1,
  claim_id: null,
  cap: 5,
  status: "running",
  todos: [],
  summary: null,
  problem: null,
  started_at: "2026-11-24T10:00:00+00:00",
  finished_at: null,
  ...overrides,
});

const TODOS: Run["todos"] = [
  { claim_id: "CLM-1001", content: "Flight canceled", status: "done" },
  { claim_id: "CLM-1002", content: "Lost bag", status: "in_progress" },
  { claim_id: "CLM-1003", content: "Hotel", status: "todo" },
  { claim_id: "CLM-1004", content: "Model down twice", status: "handler" },
];

it("shows an empty state before any run", async () => {
  fakeFetch({ "GET /api/runs/latest": null });
  render(<RunPanel />);
  expect(await screen.findByText("The agent has not run yet.")).toBeDefined();
  expect(
    screen
      .getByRole("button", { name: "Run the queue" })
      .hasAttribute("disabled"),
  ).toBe(false);
});

it("shows each to-do state and the summary", async () => {
  fakeFetch({
    "GET /api/runs/latest": run({
      status: "finished",
      todos: TODOS,
      summary: "Two claims decided, one left for a handler.",
      finished_at: "2026-11-24T10:05:00+00:00",
    }),
  });
  render(<RunPanel />);
  const list = within(await screen.findByLabelText("To-do list"));
  expect(list.getAllByRole("listitem")).toHaveLength(4);
  expect(list.getByText("Done").className).toBe("chip chip-todo-done");
  expect(list.getByText("In progress")).toBeDefined();
  expect(list.getByText("To do")).toBeDefined();
  expect(list.getByText("Left for a handler")).toBeDefined();
  expect(
    list.getByRole("link", { name: "CLM-1004" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1004");
  expect(screen.getByText("Finished")).toBeDefined();
  expect(screen.getByText("The queue, up to 5 claims")).toBeDefined();
  expect(screen.getByText(/^Started .*, ended /)).toBeDefined();
  expect(
    screen.getByText("Two claims decided, one left for a handler."),
  ).toBeDefined();
});

it("shows a running run planning its work, and blocks a second run", async () => {
  fakeFetch({ "GET /api/runs/latest": run({ claim_id: "CLM-1003", cap: 1 }) });
  render(<RunPanel />);
  expect(
    await screen.findByText("The agent is planning its work..."),
  ).toBeDefined();
  expect(screen.getByText("CLM-1003 only")).toBeDefined();
  expect(screen.getByText("Running")).toBeDefined();
  expect(
    screen
      .getByRole("button", { name: "Run the queue" })
      .hasAttribute("disabled"),
  ).toBe(true);
});

it("shows why a run failed", async () => {
  fakeFetch({
    "GET /api/runs/latest": run({
      status: "failed",
      problem: "The run stopped with an error: model unavailable",
    }),
  });
  render(<RunPanel />);
  expect(
    await screen.findByText("The run stopped with an error: model unavailable"),
  ).toBeDefined();
  expect(screen.queryByLabelText("To-do list")).toBeNull();
});

it("runs the queue with the cap and shows the list filling in", async () => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  let latest: Run | null = null;
  const fetch = fakeFetch({
    "GET /api/runs/latest": () => latest,
    "POST /api/runs": () => {
      latest = run({ cap: 3 });
      return latest;
    },
  });
  render(<RunPanel />);
  await screen.findByText("The agent has not run yet.");
  fireEvent.change(screen.getByLabelText("Claims to work"), {
    target: { value: "3" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run the queue" }));
  expect(await screen.findByText("Running")).toBeDefined();
  const post = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect(post?.[1]?.body).toBe(JSON.stringify({ cap: 3 }));

  latest = run({ cap: 3, todos: TODOS.slice(0, 2) });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
});

it("shows the refusal when a run is already going", async () => {
  fakeFetch({
    "GET /api/runs/latest": null,
    "POST /api/runs": Response.json(
      { detail: "A run is already going; wait for it to finish" },
      { status: 409 },
    ),
  });
  render(<RunPanel />);
  await screen.findByText("The agent has not run yet.");
  fireEvent.click(screen.getByRole("button", { name: "Run the queue" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "A run is already going; wait for it to finish",
  );
});

it("does not run with a cap below one", async () => {
  fakeFetch({ "GET /api/runs/latest": null });
  render(<RunPanel />);
  await screen.findByText("The agent has not run yet.");
  fireEvent.change(screen.getByLabelText("Claims to work"), {
    target: { value: "0" },
  });
  expect(
    screen
      .getByRole("button", { name: "Run the queue" })
      .hasAttribute("disabled"),
  ).toBe(true);
});
