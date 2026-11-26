import { expect, test } from "@playwright/test";

test("the queue lists every claim and opens one", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(25);

  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page.getByText("My flight home from Rome")).toBeVisible();
  await expect(page.getByText("UnderCover Premium")).toBeVisible();
  await expect(
    page.getByText("Meridian Air cancellation notice"),
  ).toBeVisible();
});

test("the instructions are read only", async ({ page }) => {
  await page.goto("/#/instructions");
  await expect(page.getByText("You are the UnderCover Agent.")).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
