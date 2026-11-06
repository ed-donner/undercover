import { expect, test } from "@playwright/test";

test("a claim's detail page shows its story, customer, policy and event log", async ({
  page,
}) => {
  await page.goto("/claims/CLM-1002");

  await expect(page.getByText(/connection in Frankfurt/)).toBeVisible();
  await expect(page.getByText("tom.becker@example.com")).toBeVisible();
  await expect(page.getByText("UnderCover Premium plan")).toBeVisible();
  await expect(page.getByText("Nothing yet.")).toBeVisible();
});

test("the instructions page shows the agent's instructions", async ({
  page,
}) => {
  await page.goto("/instructions");

  await expect(
    page.getByRole("heading", { name: "The UnderCover Agent's instructions" }),
  ).toBeVisible();
  await expect(
    page.getByText("using only the tools you are given"),
  ).toBeVisible();
});
