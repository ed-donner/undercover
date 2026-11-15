import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("/api/reseed");
});

test("the to-do list fills in and is ticked off", async ({ page, request }) => {
  const run = (await (
    await request.post("/api/runs", { data: { limit: 2 } })
  ).json()) as { id: number };
  const todos = `/api/runs/${String(run.id)}/todos`;
  await request.put(todos, {
    data: {
      items: [
        { text: "CLM-1001", status: "in_progress" },
        { text: "CLM-1002", status: "todo" },
      ],
    },
  });
  await page.goto("/");
  const list = page.getByRole("list", { name: "To-do list" });
  await expect(list).toContainText("CLM-1002");
  await expect(list).toContainText("In progress");

  await request.put(todos, {
    data: {
      items: [
        { text: "CLM-1001", status: "done" },
        { text: "CLM-1002", status: "in_progress" },
      ],
    },
  });
  await expect(list.getByText("Done")).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Waiting" }).first(),
  ).toBeVisible();
});

test("a claim page shows the steps and the sections read", async ({
  page,
  request,
}) => {
  const run = (await (
    await request.post("/api/runs", { data: { limit: 1 } })
  ).json()) as { id: number };
  await request.post(`/api/runs/${String(run.id)}/claims/CLM-1001`);
  await request.post("/api/claims/CLM-1001/read-section", {
    data: { document: "claims_manual", number: 9 },
  });
  await page.goto("/#/claims/CLM-1001");
  await expect(page.getByRole("list", { name: "Sections read" })).toContainText(
    "claims_manual section 9: Repeat claims",
  );
  await expect(page.getByRole("list", { name: "Steps" })).toContainText(
    "Started in run",
  );
});

test("the instructions page shows both instructions", async ({ page }) => {
  await page.goto("/#/instructions");
  await expect(
    page.getByRole("heading", { name: "Running the queue" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Working a claim" }),
  ).toBeVisible();
});

test("a payout over the limit waits for sign-off", async ({
  page,
  request,
}) => {
  const run = (await (
    await request.post("/api/runs", { data: { limit: 1 } })
  ).json()) as { id: number };
  await request.post(`/api/runs/${String(run.id)}/claims/CLM-1001`);
  await request.post("/api/claims/CLM-1001/decision", {
    data: {
      decision: "approve",
      payout: 1250,
      policy_section: "Wording section 3",
      reason: "Covered delay.",
    },
  });
  await page.goto("/#/claims/CLM-1001");
  const button = page.getByRole("button", { name: /Sign off and pay/ });
  await expect(button).toBeEnabled();
  await button.click();
  await expect(page.getByText(/signed off by/)).toBeVisible();
});
