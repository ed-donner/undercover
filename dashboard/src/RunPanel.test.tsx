import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Run } from "./api";
import { RunPanel } from "./RunPanel";
import { stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function run(overrides: Partial<Run> = {}): Run {
  return {
    run_id: 3,
    todos: [],
    summary: null,
    started_at: "2026-11-06T10:02:00+00:00",
    finished_at: null,
    ...overrides,
  };
}

const todos: Run["todos"] = [
  { content: "Work CLM-1001", status: "done" },
  { content: "Work CLM-1002", status: "in_progress" },
  { content: "Work CLM-1003", status: "to_do" },
  { content: "Work CLM-1004", status: "left_for_handler" },
];

async function panel() {
  return screen.findByRole("region", { name: "The agent's run" });
}

it("says when the agent hasn't run yet", async () => {
  stubApi({ "GET /api/runs/latest": null });
  render(<RunPanel />);
  expect(
    within(await panel()).getByText("The agent hasn't run yet."),
  ).toBeDefined();
});

it("shows a running run planning its work", async () => {
  stubApi({ "GET /api/runs/latest": run() });
  render(<RunPanel />);
  const shown = await panel();
  expect(within(shown).getByText("Run 3")).toBeDefined();
  expect(within(shown).getByText("Running")).toBeDefined();
  expect(
    within(shown).getByText("The agent is planning its work."),
  ).toBeDefined();
});

it("shows the to-do list with each item's status", async () => {
  stubApi({ "GET /api/runs/latest": run({ todos }) });
  render(<RunPanel />);
  const shown = await panel();
  expect(within(shown).getByText("1 of 4 done")).toBeDefined();
  const items = within(shown).getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "DoneWork CLM-1001",
    "In progressWork CLM-1002",
    "To doWork CLM-1003",
    "Left for a handlerWork CLM-1004",
  ]);
  expect(within(items[3]).getByText("Left for a handler").className).toBe(
    "badge todo-left_for_handler",
  );
});

it("shows a finished run with its summary", async () => {
  stubApi({
    "GET /api/runs/latest": run({
      todos,
      summary: "Worked four claims.",
      finished_at: "2026-11-06T10:06:00+00:00",
    }),
  });
  render(<RunPanel />);
  const shown = await panel();
  expect(within(shown).getByText("Finished")).toBeDefined();
  expect(within(shown).getByText("Worked four claims.")).toBeDefined();
  expect(within(shown).queryByText("Running")).toBeNull();
});

it("says when a finished run kept no to-do list", async () => {
  stubApi({
    "GET /api/runs/latest": run({
      summary: "No claims are waiting.",
      finished_at: "2026-11-06T10:02:01+00:00",
    }),
  });
  render(<RunPanel />);
  expect(
    within(await panel()).getByText("The agent kept no to-do list."),
  ).toBeDefined();
});

it("ticks off the to-do list as the run goes on", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes = {
    "GET /api/runs/latest": run({
      todos: [{ content: "Work CLM-1001", status: "in_progress" }],
    }),
  };
  stubApi(routes);
  render(<RunPanel />);
  expect(within(await panel()).getByText("In progress")).toBeDefined();
  routes["GET /api/runs/latest"] = run({
    todos: [{ content: "Work CLM-1001", status: "done" }],
  });
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(within(await panel()).getByText("Done")).toBeDefined();
});

it("shows nothing while the run can't be loaded", () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  const { container } = render(<RunPanel />);
  expect(container.textContent).toBe("");
});
