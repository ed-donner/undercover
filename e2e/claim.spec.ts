import { expect, test } from "@playwright/test";

test("a decided claim's page shows its decision, payout and reason", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1006";
  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout: 425.0,
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

test("an over-limit approval blocks payment until a handler signs off", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1007";
  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout: 1200.0,
      reason: "A hospital admission over the approval limit.",
      policy_reference: "Section 7",
    },
  });

  await page.goto(`/claims/${claimId}`);

  await expect(
    page.getByRole("button", { name: "Release payment" }),
  ).toHaveCount(0);
  const signOff = page.getByRole("button", {
    name: "Sign off as Dana Whitfield",
  });
  await expect(signOff).toBeVisible();

  await signOff.click();

  const release = page.getByRole("button", { name: "Release payment" });
  await expect(release).toBeVisible();
  await release.click();

  await expect(page.getByText("Paid $1,200.00.")).toBeVisible();
});
