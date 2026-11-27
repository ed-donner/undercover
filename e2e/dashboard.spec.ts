import { expect, test } from "@playwright/test";

test("the queue lists every claim with its state", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  const rows = page.locator("tbody tr");
  await expect(rows).toHaveCount(25);
  const first = rows.filter({ hasText: "CLM-1001" });
  await expect(first).toContainText("Maya Patel");
  await expect(first).toContainText("$420.00");
  await expect(first).toContainText("Waiting");
});

test("a claim shows its story and items", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page.getByText("My flight home from Rome")).toBeVisible();
  const items = page.getByRole("table").locator("tbody tr");
  await expect(items).toHaveCount(3);
  await expect(page.getByText("UnderCover Premium")).toBeVisible();
  await expect(
    page.getByText("The agent has not decided this claim yet."),
  ).toBeVisible();
});

test("the instructions are shown read only", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(page.getByText("You are the UnderCover Agent.")).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
