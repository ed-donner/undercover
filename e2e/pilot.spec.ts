import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

async function approve(
  request: APIRequestContext,
  claimId: string,
  payout: number,
) {
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout,
      explanation: "The loss is covered by the wording.",
      policy_section: "5. Baggage and Personal Effects",
    },
  });
  expect(response.ok()).toBe(true);
}

// Each test uses its own claim, because the database is reset once, when the backend starts.
test("the queue shows every claim", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /^CLM-/ })).toHaveCount(25);
});

test("a claim shows its decision and reasons", async ({ page, request }) => {
  await approve(request, "CLM-1001", 420);
  await page.goto("/#/claims/CLM-1001");
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  await expect(
    page.getByText("The loss is covered by the wording."),
  ).toBeVisible();
  await expect(page.getByText("5. Baggage and Personal Effects")).toBeVisible();
  await expect(page.getByText("Maya Patel").first()).toBeVisible();

  await page.goto("/");
  const row = page.getByRole("row", { name: /CLM-1001/ });
  await expect(row).toContainText("Approved");
  await expect(row).toContainText("$420.00");
});

test("a payout over $1,000 waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await approve(request, "CLM-1002", 1500);
  const refused = await request.post("/api/claims/CLM-1002/payment", {
    data: { amount: 1500 },
  });
  expect(refused.status()).toBe(409);

  await page.goto("/#/claims/CLM-1002");
  await expect(page.getByText("Waiting for sign-off")).toBeVisible();
  await expect(
    page.getByText(/blocked until a handler signs it off/),
  ).toBeVisible();
  await page
    .getByLabel("Signing off as")
    .selectOption({ label: "Dana Whitfield" });
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.getByText(/signed off by Dana Whitfield/)).toBeVisible();
  await expect(page.getByText("Decided")).toBeVisible();
});

test("a payout of $1,000 pays without sign-off", async ({ page, request }) => {
  await approve(request, "CLM-1003", 1000);
  const paid = await request.post("/api/claims/CLM-1003/payment", {
    data: { amount: 1000 },
  });
  expect(paid.ok()).toBe(true);

  await page.goto("/#/claims/CLM-1003");
  await expect(page.getByText(/Paid\s+\$1,000\.00/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sign off and pay" }),
  ).toHaveCount(0);
});

test("the instructions are shown and cannot be edited", async ({ page }) => {
  await page.goto("/#/instructions");
  await expect(
    page.getByRole("heading", { name: "How to work" }),
  ).toBeVisible();
  await expect(page.getByText("You are the UnderCover Agent.")).toBeVisible();
  await expect(page.locator("textarea, input, [contenteditable]")).toHaveCount(
    0,
  );
});
