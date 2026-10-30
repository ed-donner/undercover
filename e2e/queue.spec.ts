import { expect, test } from "@playwright/test";

test("the queue page lists the claims", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "The claims queue" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
});

test("the queue shows a claim's status as it moves through the four states", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1005";
  const row = () => page.getByRole("row", { name: new RegExp(claimId) });

  await page.goto("/");
  await expect(row()).toContainText("waiting");

  await request.post(`/api/claims/${claimId}/steps`, {
    data: {
      text: "Read the claim, its policy and the customer's claim history",
    },
  });
  await page.goto("/");
  await expect(row()).toContainText("in progress");

  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout: 1250,
      reason: "A passport lost while swimming, replaced abroad.",
      policy_reference: "Section 6",
    },
  });
  await page.goto("/");
  await expect(row()).toContainText("waiting for sign-off");

  await request.post(`/api/claims/${claimId}/sign-off`, {
    data: { handler_id: "HND-01" },
  });
  await page.goto("/");
  await expect(row()).toContainText("decided");
});

test("the queue page shows the current run's to-do list in every status", async ({
  page,
  request,
}) => {
  const claimIds = ["CLM-1010", "CLM-1012", "CLM-1013", "CLM-1014"];
  const run = (await (
    await request.post("/api/runs", { data: { claim_ids: claimIds } })
  ).json()) as { run_id: number };
  const runPath = `/api/runs/${String(run.run_id)}/items`;

  await request.post(`${runPath}/${claimIds[0]}`, {
    data: { status: "done", note: "Approved for $420.00." },
  });
  await request.post(`${runPath}/${claimIds[1]}`, {
    data: { status: "in progress", note: "" },
  });
  await request.post(`${runPath}/${claimIds[2]}`, {
    data: { status: "left for a handler", note: "Failed twice." },
  });
  // claimIds[3] stays "to do".

  await page.goto("/");

  await expect(page.getByText("The current run")).toBeVisible();
  const items = page.locator("li");
  await expect(items.filter({ hasText: claimIds[0] })).toContainText("done");
  await expect(items.filter({ hasText: claimIds[1] })).toContainText(
    "in progress",
  );
  await expect(items.filter({ hasText: claimIds[2] })).toContainText(
    "left for a handler",
  );
  await expect(items.filter({ hasText: claimIds[3] })).toContainText("to do");
});
