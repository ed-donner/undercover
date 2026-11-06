import { expect, test } from "@playwright/test";

test("both sets of the agent's instructions are shown read only", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Running the queue" })
      .getByText(/running the claims queue/),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Working a claim" })
      .getByText(/^You are the UnderCover Agent\. You decide/),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("button")).toHaveCount(0);
});
