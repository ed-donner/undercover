import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { RunPanel } from "./RunPanel";
import type { Run } from "./types";

afterEach(cleanup);

const run = (overrides: Partial<Run> = {}): Run => ({
  run_id: 1,
  limit: 5,
  status: "running",
  summary: "",
  started_at: "2026-10-19T09:00:00+00:00",
  finished_at: null,
  todos: [],
  ...overrides,
});

it("shows the to-do list with each item's state", () => {
  render(
    <RunPanel
      run={run({
        todos: [
          { text: "CLM-1001, trip delay", status: "done" },
          { text: "CLM-1002, baggage", status: "in_progress" },
          { text: "CLM-1003, medical", status: "todo" },
          { text: "CLM-1004, theft", status: "left_for_handler" },
        ],
      })}
    />,
  );
  expect(screen.getByText("Current run")).toBeDefined();
  expect(screen.getByText("Running")).toBeDefined();
  expect(screen.getByText("Done").className).toContain("chip-todo-done");
  expect(screen.getByText("In progress").className).toContain(
    "chip-todo-in_progress",
  );
  expect(screen.getByText("To do").className).toContain("chip-todo-todo");
  expect(screen.getByText("Left for a handler").className).toContain(
    "chip-todo-left_for_handler",
  );
  expect(screen.getByText("CLM-1004, theft")).toBeDefined();
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
});

it("says the agent is planning before it has a list", () => {
  render(<RunPanel run={run({ limit: 1 })} />);
  expect(screen.getByText("The agent is planning its work.")).toBeDefined();
  expect(screen.getByText(/Up to/).textContent).toBe("Up to 1 claim");
});

it("shows the summary once the run has finished", () => {
  render(
    <RunPanel
      run={run({ status: "finished", summary: "Worked five claims." })}
    />,
  );
  expect(screen.getByText("Last run")).toBeDefined();
  expect(screen.getByText("Finished")).toBeDefined();
  expect(screen.getByText("Worked five claims.")).toBeDefined();
  expect(screen.getByText("The agent made no plan.")).toBeDefined();
});

it("shows a failed run", () => {
  render(<RunPanel run={run({ status: "failed", summary: "It broke." })} />);
  expect(screen.getByText("Failed").className).toContain("chip-run-failed");
});
