import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const todos = (...items: [string, string][]) => ({
  todos: items.map(([text, status]) => ({ text, status })),
});

test("the to-do list fills in and is ticked off while the page is open", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByText("Current run")).toBeHidden();

  await request.post("/api/runs", { data: { limit: 3 } });
  await request.put("/api/runs/1/todos", {
    data: todos(
      ["CLM-1010, trip delay", "in_progress"],
      ["CLM-1011, baggage", "todo"],
    ),
  });
  await expect(page.getByText("Current run")).toBeVisible();
  await expect(page.getByText("CLM-1011, baggage")).toBeVisible();
  await expect(page.getByText("To do", { exact: true })).toBeVisible();

  await request.put("/api/runs/1/todos", {
    data: todos(
      ["CLM-1010, trip delay", "done"],
      ["CLM-1011, baggage", "in_progress"],
    ),
  });
  await expect(page.getByText("Done", { exact: true })).toBeVisible();
  await expect(page.getByText("To do", { exact: true })).toBeHidden();

  await request.post("/api/runs/1/finish", {
    data: { summary: "Worked two claims.", status: "finished" },
  });
  await expect(page.getByText("Last run")).toBeVisible();
  await expect(page.getByText("Worked two claims.")).toBeVisible();
});

test("a run cannot take more claims than its cap", async ({
  page,
  request,
}) => {
  await request.post("/api/runs", { data: { limit: 2 } });
  expect((await request.post("/api/runs/2/claims/CLM-1010")).ok()).toBe(true);
  expect((await request.post("/api/runs/2/claims/CLM-1011")).ok()).toBe(true);
  const refused = await request.post("/api/runs/2/claims/CLM-1012");
  expect(refused.status()).toBe(409);
  await request.post("/api/runs/2/finish", {
    data: { summary: "", status: "finished" },
  });
  await page.goto("/");
  await expect(page.getByText("Up to 2 claims")).toBeVisible();
  await expect(page.getByRole("row", { name: /CLM-1012/ })).toContainText(
    "Waiting",
  );
});

test("a claim that fails twice is left for a handler", async ({
  page,
  request,
}) => {
  for (const attempt of [1, 2]) {
    await request.post("/api/claims/CLM-1012/start");
    const failed = await request.post("/api/claims/CLM-1012/fail", {
      data: { reason: "The model timed out." },
    });
    const claim = (await failed.json()) as { status: string };
    expect(claim.status).toBe(attempt === 1 ? "waiting" : "needs_handler");
  }
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Needs a handler 1" }),
  ).toBeVisible();
  await expect(page.getByRole("row", { name: /CLM-1012/ })).toContainText(
    "Needs a handler",
  );
  await page.goto("/#/claims/CLM-1012");
  await expect(page.getByText(/A handler needs to work it/)).toBeVisible();
  await expect(
    page.getByText(/Failed 2 times: left for a handler/),
  ).toBeVisible();
});

test("a claim shows the sections the agent read", async ({ page, request }) => {
  await request.post("/api/claims/CLM-1013/start");
  for (const text of [
    "Claims manual, 9. Repeat claims",
    "Policy wording, 3. Trip Delay",
  ]) {
    await request.post("/api/claims/CLM-1013/steps", {
      data: { kind: "read", text },
    });
  }
  await page.goto("/#/claims/CLM-1013");
  await expect(
    page.getByRole("heading", { name: "What the agent read" }),
  ).toBeVisible();
  await expect(page.getByText("Claims manual, 9. Repeat claims")).toHaveCount(
    2,
  );
  await expect(page.getByText("Policy wording, 3. Trip Delay")).toHaveCount(2);
});

test("the instructions page shows both sets of instructions", async ({
  page,
}) => {
  await page.goto("/#/instructions");
  await expect(
    page.getByRole("heading", { name: "Running the queue" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Working a claim" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Before you finish, call `check_queue`/),
  ).toBeVisible();
});
