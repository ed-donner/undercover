import { expect, test } from "@playwright/test";

test("the queue page lists the claims", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "The claims queue" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
});
