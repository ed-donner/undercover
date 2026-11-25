import { expect, test, type APIRequestContext } from "@playwright/test";

async function post(request: APIRequestContext, path: string, data?: object) {
  const response = await request.post(path, { data });
  expect(response.ok()).toBe(true);
  return (await response.json()) as { id: number };
}

const todo = (claim_id: string, content: string, status: string) => ({
  claim_id,
  content,
  status,
});

test("a run started from the queue page shows its to-do list and summary", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const panel = page.getByLabel("Current run");
  await panel.getByLabel("Claims to work").fill("2");
  await panel.getByRole("button", { name: "Run the queue" }).click();
  await expect(panel.getByText("Running")).toBeVisible();
  await expect(panel.getByText("The queue, up to 2 claims")).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Run the queue" }),
  ).toBeDisabled();

  const run = (await (await request.get("/api/runs/latest")).json()) as {
    id: number;
  };
  await post(request, `/api/runs/${String(run.id)}/todos`, {
    todos: [
      todo("CLM-1005", "Passport eaten by a giraffe", "in_progress"),
      todo("CLM-1006", "Falling coconut", "todo"),
    ],
  });
  const list = page.getByLabel("To-do list");
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(list.getByText("In progress")).toBeVisible();

  await post(request, `/api/runs/${String(run.id)}/todos`, {
    todos: [
      todo("CLM-1005", "Approve, $243.00, paid", "done"),
      todo("CLM-1006", "Approve, $375.00, paid", "done"),
    ],
  });
  await expect(list.getByText("Done")).toHaveCount(2);
  await post(request, `/api/runs/${String(run.id)}/finish`, {
    summary: "Two claims approved and paid, $618.00 in all.",
  });
  await expect(panel.getByText("Finished")).toBeVisible();
  await expect(
    panel.getByText("Two claims approved and paid, $618.00 in all."),
  ).toBeVisible();
});

test("a claim that fails twice is left for a handler with both problems", async ({
  page,
  request,
}) => {
  for (const problem of [
    "The model provider timed out",
    "It timed out again",
  ]) {
    await post(request, "/api/claims/CLM-1007/start");
    await post(request, "/api/claims/CLM-1007/release", { problem });
  }
  await page.goto("/");
  const row = page.getByRole("row", { name: /CLM-1007/ });
  await expect(row.getByText("Left for a handler")).toBeVisible();

  await row.getByRole("link", { name: "CLM-1007" }).click();
  const steps = page.getByLabel("Agent steps");
  await expect(steps.getByText("The model provider timed out")).toBeVisible();
  await expect(steps.getByText("Attempt 2")).toBeVisible();
  await expect(steps.getByText("It timed out again")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run agent" })).toHaveCount(0);
});

test("a claim's page lists the sections the agent read", async ({
  page,
  request,
}) => {
  for (const content of [
    "Policy wording, 6. Passport and Travel Documents",
    "Claims manual, 7. Interpretation notes",
  ]) {
    await post(request, "/api/claims/CLM-1009/steps", {
      kind: "read",
      content,
    });
  }
  await page.goto("/#/claims/CLM-1009");
  const reads = page.getByLabel("What the agent read");
  await expect(reads.getByRole("listitem")).toHaveText([
    "Policy wording, 6. Passport and Travel Documents",
    "Claims manual, 7. Interpretation notes",
  ]);
});
