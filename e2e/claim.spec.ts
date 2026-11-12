import { expect, test } from "@playwright/test";

test("a decided claim's page shows its decision, payout and reason", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1006";
  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout: "425.00",
      reason: "A covered trip delay with receipts.",
      policy_reference: "Section 3",
    },
  });

  await page.goto(`/claims/${claimId}`);

  await expect(page.getByText("approve, $425.00")).toBeVisible();
  await expect(
    page.getByText("A covered trip delay with receipts."),
  ).toBeVisible();
  await expect(page.getByText("Section 3")).toBeVisible();
});

test("the instructions page shows the agent's instructions", async ({
  page,
}) => {
  await page.goto("/instructions");

  await expect(
    page.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeVisible();
  await expect(page.getByText("calling decide_claim once")).toBeVisible();
});

test("a sign-off reaches the agent, and the claim shows as paid once it pays", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1007";
  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout: "1200.00",
      reason: "A hospital admission over the approval limit.",
      policy_reference: "Section 7",
    },
  });

  await page.goto(`/claims/${claimId}`);

  await expect(page.getByRole("button", { name: /Release/ })).toHaveCount(0);
  await page
    .getByRole("button", { name: "Sign off as Dana Whitfield" })
    .click();

  await expect(page.getByText("Payment in progress.")).toBeVisible();
  const calls = await request.get("http://127.0.0.1:8003/calls");
  const paths = (await calls.json()) as string[];
  expect(paths.filter((path) => path.includes(claimId))).toEqual([
    `/api/claims/${claimId}/resume`,
  ]);

  await request.post(`/api/claims/${claimId}/payment`, {
    data: { amount: "1200.00" },
  });

  await expect(page.getByText("Paid $1,200.00.")).toBeVisible();
  await expect(page.getByText(/Signed off by Dana Whitfield on/)).toBeVisible();
});
