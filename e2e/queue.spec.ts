import { expect, test } from "@playwright/test";

test("the queue lists the 25 claims with where each one stands", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  const claims = page.getByRole("region", { name: "Claims", exact: true });
  await expect(claims.getByRole("row")).toHaveCount(26);
  const last = claims.getByRole("row", { name: /CLM-1025/ });
  await expect(last.getByText("Waiting")).toBeVisible();
  await expect(last.getByText("$71.00")).toBeVisible();
});
