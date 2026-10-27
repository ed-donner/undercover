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
