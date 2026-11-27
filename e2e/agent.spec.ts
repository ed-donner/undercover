import { type APIRequestContext, expect, test } from "@playwright/test";

// These tests act as the agent through the API, so no test calls a model.

async function post(request: APIRequestContext, path: string, data = {}) {
  const response = await request.post(path, { data });
  return response.status();
}

test("the claim page shows the agent's steps in order", async ({
  page,
  request,
}) => {
  expect(await post(request, "/api/claims/CLM-1003/start")).toBe(200);
  for (const content of ["get_claim {}", "get_policy_wording {}"]) {
    await post(request, "/api/claims/CLM-1003/steps", {
      kind: "tool_call",
      content,
    });
  }
  await page.goto("/#/claims/CLM-1003");
  await expect(page.getByText("In progress").first()).toBeVisible();
  await expect(page.getByRole("status")).toHaveText(
    "The agent is working on this claim.",
  );
  const steps = page.locator(".steps li");
  await expect(steps).toHaveCount(2);
  await expect(steps.nth(0)).toContainText("get_claim {}");
  await expect(steps.nth(1)).toContainText("get_policy_wording {}");

  await post(request, "/api/claims/CLM-1003/steps", {
    kind: "message",
    content: "Referred for a handler.",
  });
  await expect(steps).toHaveCount(3);
});

test("a payout over $1,000 waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await post(request, "/api/claims/CLM-1004/start");
  await post(request, "/api/claims/CLM-1004/decision", {
    decision: "approve",
    payout: 1500,
    calculation: "1500",
    reasons: "Covered by the policy.",
    policy_section: "4. Baggage Delay",
  });
  expect(
    await post(request, "/api/claims/CLM-1004/payment", { amount: 1500 }),
  ).toBe(403);

  await page.goto("/");
  await expect(
    page.locator("tbody tr").filter({ hasText: "CLM-1004" }),
  ).toContainText("Waiting for sign-off");

  await page.getByRole("link", { name: "CLM-1004" }).click();
  await expect(page.getByText(/payment is\s+blocked/)).toBeVisible();
  await expect(page.getByText("Not paid")).toBeVisible();
  await page
    .getByLabel("Handler")
    .selectOption({ label: "Dana Whitfield, Senior Claims Handler" });
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.getByText(/^Paid \$1,500\.00/)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Decided",
  );
});
