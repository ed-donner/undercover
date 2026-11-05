import { expect, test } from "@playwright/test";

const CLAIM_ID = "CLM-1010";

test("a handler can sign off a claim waiting for sign-off, releasing its payment", async ({
  page,
  request,
}) => {
  await request.post(`/api/claims/${CLAIM_ID}/decide`, {
    data: {
      decision: "approve",
      payout: 2000,
      reason: "A valid claim over the sign-off limit.",
      reference: "Policy wording, section 7",
    },
  });
  await request.post(`/api/claims/${CLAIM_ID}/pay`, { data: { amount: 2000 } });

  await page.goto(`/claims/${CLAIM_ID}`);
  await expect(page.getByText("Waiting for sign-off")).toBeVisible();

  await page.getByRole("button", { name: "Sign off" }).click();

  await expect(page.getByText("Decided", { exact: true })).toBeVisible();
  await expect(page.getByText("Paid $2,000.00", { exact: true })).toBeVisible();
});
