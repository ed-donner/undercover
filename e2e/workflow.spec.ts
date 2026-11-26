import { expect, test } from "@playwright/test";
import { decide } from "./helpers";

test("steps appear on the claim page as the agent works", async ({
  page,
  request,
}) => {
  await page.goto("/#/claims/CLM-1005");
  await expect(
    page.getByText("The agent has not started on this claim."),
  ).toBeVisible();

  await request.post("/api/claims/CLM-1005/start");
  await request.post("/api/claims/CLM-1005/steps", {
    data: { text: "Calling get_policy with CLM-1005" },
  });
  await expect(
    page.getByText("Calling get_policy with CLM-1005"),
  ).toBeVisible();
  await expect(
    page.locator(".claim-header").getByText("In progress"),
  ).toBeVisible();
});

test("a payout over $1,000 waits for sign-off, then is paid", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1003", "approve", 1500);
  const blocked = await request.post("/api/claims/CLM-1003/payment", {
    data: { amount: 1500 },
  });
  expect(blocked.status()).toBe(409);

  await page.goto("/#/claims/CLM-1003");
  const signOff = page.getByRole("region", { name: "Sign-off" });
  await expect(signOff.getByText("Waiting for sign-off")).toBeVisible();
  await signOff.getByLabel("Handler").selectOption({ label: "Dana Whitfield" });
  await signOff
    .getByRole("button", { name: "Sign off and pay $1,500.00" })
    .click();

  await expect(page.getByText("signed off by Dana Whitfield")).toBeVisible();
  await expect(
    page.locator(".claim-header").getByText("Decided"),
  ).toBeVisible();
  await expect(signOff).toHaveCount(0);

  await page.getByRole("link", { name: "Back to the queue" }).click();
  const row = page.getByRole("row").filter({ hasText: "CLM-1003" });
  await expect(row.getByText("Decided")).toBeVisible();
  await expect(row.getByText("$1,500.00")).toBeVisible();
});

test("a declined claim shows its reasons and no sign-off", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1004", "decline", 0);
  await page.goto("/#/claims/CLM-1004");
  await expect(page.getByText("Decision: Declined")).toBeVisible();
  await expect(
    page.getByText("The agent's reason for CLM-1004."),
  ).toBeVisible();
  await expect(
    page.getByText("Section 5, Baggage and Personal Effects"),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Sign-off" })).toHaveCount(0);
});
