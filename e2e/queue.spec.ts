import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";

test("the dashboard shows the backend is up and the waiting queue", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("Backend: up")).toBeVisible();
  await expect(page.getByText("CLM-1001")).toBeVisible();
});

test("the queue shows the to-do list and the claim page shows steps and sections read", async ({
  page,
  request,
}) => {
  const run = (await (
    await request.post(`${API}/api/runs`, { data: { cap: 2 } })
  ).json()) as { run_id: number };
  await request.put(`${API}/api/runs/${String(run.run_id)}/todos`, {
    data: {
      items: [
        { claim_id: "CLM-1001", text: "Work CLM-1001", state: "todo" },
        { claim_id: "CLM-1002", text: "Work CLM-1002", state: "todo" },
      ],
    },
  });
  await request.post(
    `${API}/api/runs/${String(run.run_id)}/claims/CLM-1001/start`,
  );
  await request.post(`${API}/api/claims/CLM-1001/reads`, {
    data: { document: "manual", number: 4 },
  });
  await request.post(`${API}/api/claims/CLM-1001/steps`, {
    data: { tool: "read_section", summary: "manual section 4" },
  });
  await request.post(`${API}/api/claims/CLM-1001/decision`, {
    data: {
      decision: "decline",
      payout: 0,
      section: "Manual 4",
      reason: "Not covered.",
    },
  });

  await page.goto("/");
  const todos = page.locator(".todos");
  await expect(todos.getByText("Work CLM-1001")).toBeVisible();
  await expect(todos.getByText("Work CLM-1002")).toBeVisible();
  await expect(page.getByText("Waiting").first()).toBeVisible();

  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page.getByText("Sections read")).toBeVisible();
  await expect(page.getByText(/Manual section 4/)).toBeVisible();
  await expect(page.locator("ol").getByText("manual section 4")).toBeVisible();
  await expect(page.getByText("Not covered.")).toBeVisible();
});

test("the instructions page shows both instruction texts", async ({ page }) => {
  await page.goto("/#/instructions");
  await expect(
    page.getByRole("heading", { name: "Queue runner instructions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Claim instructions" }),
  ).toBeVisible();
});
