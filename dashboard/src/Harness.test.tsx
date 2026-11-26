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
import { App } from "./App";
import { ClaimActions, DecisionPanel } from "./DecisionPanel";
import { QueueRunPanel } from "./QueueRunPanel";
import { ClaimSources, SourceLibrary } from "./Sources";
import type { AgentRun, SourceRead, TaskState } from "./types";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function run(state: TaskState = "todo"): AgentRun {
  return {
    run_id: "queue-1",
    status: "running",
    max_claims: 5,
    summary: "",
    error: null,
    tasks: [
      {
        task_id: "task-1",
        claim_id: "CLM-1001",
        state,
        reason: "Planned work",
        admitted: false,
      },
    ],
  };
}

it("validates caps and starts capped and whole-queue runs", async () => {
  const data = fixture();
  const reload = vi.fn();
  render(
    <QueueRunPanel
      runs={[]}
      error={undefined}
      eligible={5}
      reload={reload}
      select={vi.fn()}
    />,
  );
  expect(screen.getByText("No agent runs yet.")).toBeDefined();
  const cap = screen.getByLabelText("Claim cap");
  for (const value of ["0", "-1", "1.5", ""]) {
    fireEvent.change(cap, { target: { value } });
    expect(
      screen.getByRole("button", { name: "Start capped run" }),
    ).toHaveProperty("disabled", true);
  }
  fireEvent.change(cap, { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Start capped run" }));
  await waitFor(() => {
    expect(reload).toHaveBeenCalledOnce();
  });
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/agent-runs",
    expect.objectContaining({ body: '{"mode":"queue","max_claims":5}' }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Start queue" }));
  await waitFor(() => {
    expect(reload).toHaveBeenCalledTimes(2);
  });
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/agent-runs",
    expect.objectContaining({ body: '{"mode":"queue","max_claims":null}' }),
  );
});

it("shows loading and errors without pretending a start succeeded", async () => {
  const data = fixture();
  const reload = vi.fn();
  const props = { error: undefined, eligible: 5, reload, select: vi.fn() };
  const view = render(<QueueRunPanel {...props} runs={undefined} />);
  expect(screen.getByText("Loading run…")).toBeDefined();
  expect(screen.getByRole("button", { name: "Start queue" })).toHaveProperty(
    "disabled",
    true,
  );
  view.rerender(<QueueRunPanel {...props} runs={[]} />);
  data.fetcher.mockRejectedValueOnce(new Error("Another agent run is active"));
  fireEvent.click(screen.getByRole("button", { name: "Start queue" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Another agent run is active Refresh run",
  );
  expect(screen.queryByText("Agent working the queue")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Refresh run" }));
  expect(reload).toHaveBeenCalledTimes(2);
  view.rerender(
    <QueueRunPanel {...props} runs={[]} eligible={0} error="Run unavailable" />,
  );
  expect(screen.getByRole("button", { name: "Start queue" })).toHaveProperty(
    "disabled",
    true,
  );
});

it("shows ordered task states, navigation, summary and terminal errors", () => {
  fixture();
  const select = vi.fn();
  const active = run();
  active.tasks = (
    ["todo", "in_progress", "done", "needs_handler"] as const
  ).map((state, index) => ({
    ...active.tasks[0],
    task_id: `task-${String(index)}`,
    claim_id: `CLM-${String(1001 + index)}`,
    state,
  }));
  const props = { error: undefined, eligible: 5, reload: vi.fn(), select };
  const view = render(<QueueRunPanel {...props} runs={[active]} />);
  for (const label of ["To do", "In progress", "Done", "Left for a handler"])
    expect(screen.getByText(label)).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Review CLM-1002" }));
  expect(select).toHaveBeenCalledWith("CLM-1002");
  expect(screen.getByRole("button", { name: "Start queue" })).toHaveProperty(
    "disabled",
    true,
  );
  active.tasks = [];
  view.rerender(<QueueRunPanel {...props} runs={[{ ...active }]} />);
  expect(
    screen.getByText("The agent is preparing its to-do list."),
  ).toBeDefined();
  view.rerender(
    <QueueRunPanel
      {...props}
      runs={[
        {
          ...active,
          status: "failed",
          error: "Agent could not finish.",
          summary: "One claim left for review.",
        },
      ]}
    />,
  );
  expect(screen.getByText("Run failed")).toBeDefined();
  expect(screen.getByRole("alert")).toHaveProperty(
    "textContent",
    "Agent could not finish.",
  );
  expect(screen.getByText("One claim left for review.")).toBeDefined();
});

it("polls persisted tasks and keeps the final run after remount", async () => {
  const data = fixture();
  data.responses.set("/api/agent-runs", [run()]);
  vi.useFakeTimers();
  const view = render(<App />);
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(screen.getByText("To do")).toBeDefined();
  expect(screen.getByRole("button", { name: /Process claim/ })).toHaveProperty(
    "disabled",
    true,
  );
  const finished = {
    ...run("done"),
    status: "completed",
    summary: "One claim completed.",
  };
  data.responses.set("/api/agent-runs", [finished]);
  await act(() => vi.advanceTimersByTimeAsync(1500));
  expect(screen.getByText("Done")).toBeDefined();
  view.unmount();
  render(<App />);
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(screen.getByText("One claim completed.")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Review CLM-1001" }));
  expect(
    screen.getByRole("heading", { name: "Maya Patel", level: 2 }),
  ).toBeDefined();
});

it("shows handler holds without automatic restart and historical provenance", () => {
  const data = fixture();
  data.claim.needs_handler = true;
  data.claim.handler_reason = "Two attempts failed";
  data.queue[0].needs_handler = true;
  render(
    <ClaimActions
      claim={data.claim}
      handlers={data.handlers}
      runs={[]}
      onChange={vi.fn()}
    />,
  );
  expect(
    screen.queryByRole("button", { name: /Process claim|Retry claim/ }),
  ).toBeNull();
  expect(
    screen.getByText(/Left for a handler: Two attempts failed/),
  ).toBeDefined();
  approve(data.claim);
  if (!data.claim.decision) throw new Error("Missing fixture decision");
  data.claim.decision.manual_version = null;
  data.claim.decision.manual_sections = [];
  render(<DecisionPanel claim={data.claim} />);
  expect(
    screen.getByText("Historical decision: manual provenance not recorded."),
  ).toBeDefined();
});

it("groups exact source reads by attempt without inventing missing ones", () => {
  const source: SourceRead = {
    sequence: 1,
    run_id: "attempt-one",
    read_at: "2026-11-13",
    document_id: "manual",
    version: "2026.2",
    section: 9,
    title: "Repeat claims",
    text: "Complete manual section text.",
  };
  render(
    <ClaimSources
      reads={[
        source,
        {
          ...source,
          sequence: 2,
          run_id: "attempt-two",
          document_id: "wording",
          version: "2026.1",
          section: 3,
          title: "Trip Delay",
          text: "Complete wording section text.",
        },
      ]}
    />,
  );
  expect(screen.getByText("Attempt attempt-one")).toBeDefined();
  expect(screen.getByText("Attempt attempt-two")).toBeDefined();
  fireEvent.click(screen.getByText(/Claims manual 2026.2/));
  expect(screen.getByText("Complete manual section text.")).toBeDefined();
  expect(screen.getByText("Complete wording section text.")).toBeDefined();
});

it("browses source sections with recoverable catalog and section errors", async () => {
  const data = fixture();
  data.fetcher.mockRejectedValueOnce(new Error("Sources offline"));
  render(<SourceLibrary />);
  expect(screen.getByText("Loading sources…")).toBeDefined();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry source list" }));
  const section = await screen.findByRole("button", { name: /Manual 2026.2/ });
  data.fetcher.mockRejectedValueOnce(new Error("Section unavailable"));
  fireEvent.click(section);
  expect(screen.getByText("Loading section…")).toBeDefined();
  await screen.findByText("Section unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Retry section" }));
  expect(
    await screen.findByText("A third claim is referred for review."),
  ).toBeDefined();
});
