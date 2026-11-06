import { expect, test } from "@playwright/test";

test("the queue lists the 25 claims with where each one stands", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  const claims = page.getByRole("region", { name: "Claims", exact: true });
  await expect(claims.getByRole("row")).toHaveCount(26);
  const last = claims.getByRole("row", { name: /CLM-1025/ });
  await expect(last.getByText("Waiting")).toBeVisible();
  await expect(last.getByText("$71.00")).toBeVisible();
});

test("the queue shows the agent's to-do list as the run goes on", async ({
  page,
  request,
}) => {
  const started = await request.post("/api/runs");
  const { run_id: runId } = (await started.json()) as { run_id: number };
  const todos = (status: string) => ({
    data: {
      todos: [
        { content: "Work CLM-1024", status },
        { content: "Work CLM-1025", status: "to_do" },
      ],
    },
  });
  await request.put(`/api/runs/${String(runId)}/todos`, todos("in_progress"));
  await page.goto("/");
  const run = page.getByRole("region", { name: "The agent's run" });
  await expect(run.getByText(`Run ${String(runId)}`)).toBeVisible();
  await expect(run.getByText("Running")).toBeVisible();
  const first = run.getByRole("listitem").first();
  await expect(first).toHaveText("In progressWork CLM-1024");
  await request.put(`/api/runs/${String(runId)}/todos`, todos("done"));
  await expect(first).toHaveText("DoneWork CLM-1024");
  await expect(run.getByText("1 of 2 done")).toBeVisible();
  await request.post(`/api/runs/${String(runId)}/finish`, {
    data: { summary: "Worked one claim and left one waiting." },
  });
  await expect(run.getByText("Finished", { exact: true })).toBeVisible();
  await expect(
    run.getByText("Worked one claim and left one waiting."),
  ).toBeVisible();
});
