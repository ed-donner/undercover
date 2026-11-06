import { expect, test } from "@playwright/test";

test("the queue lists the seeded claims, waiting to be worked", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
  await expect(page.getByRole("row", { name: /CLM-1001/ })).toContainText(
    "Waiting",
  );
  await expect(page.getByRole("button", { name: "Run" }).first()).toBeVisible();
});

test("a claim links through to its detail page", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page).toHaveURL(/\/claims\/CLM-1001$/);
  await expect(page.getByRole("heading", { name: "CLM-1001" })).toBeVisible();
});
