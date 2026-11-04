import { expect, test } from "@playwright/test";

test("a payout over $1,000 waits for a handler, whose sign-off pays it", async ({
  page,
  request,
}) => {
  expect((await request.post("/api/claims/CLM-1003/start")).ok()).toBe(true);
  const decision = await request.post("/api/claims/CLM-1003/decision", {
    data: {
      decision: "approve",
      payout: 1500,
      reason: "The treatment abroad is covered.",
      policy_section: "Section 7, Emergency Medical",
    },
  });
  expect(decision.ok()).toBe(true);

  await page.goto("/#/claims/CLM-1003");
  await expect(page.getByText("Waiting for sign-off")).toBeVisible();

  const payment = await request.post("/api/claims/CLM-1003/payment", {
    data: { amount: 1500 },
  });
  expect(payment.status()).toBe(403);

  await page.getByLabel("Handler").selectOption({ label: "Dana Whitfield" });
  await page
    .getByRole("button", { name: "Sign off and pay $1,500.00" })
    .click();
  await expect(page.getByText(/^Paid \$1,500\.00 on/)).toBeVisible();
  await expect(page.getByText(/Signed off by Dana Whitfield\./)).toBeVisible();

  await page.getByRole("link", { name: "Back to the queue" }).click();
  await expect(
    page.getByRole("row", { name: /CLM-1003/ }).getByText("Decided"),
  ).toBeVisible();
});
