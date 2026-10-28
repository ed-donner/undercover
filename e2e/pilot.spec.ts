import { expect, test } from "@playwright/test";

test("the queue shows every claim and opens one", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(
    page.getByRole("heading", { name: /CLM-1001 Flight home canceled/ }),
  ).toBeVisible();
  await expect(page.getByText("Hotel Aurelia Fiumicino.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run agent" })).toBeVisible();
});

test("the agent's steps and decision show on the claim", async ({
  page,
  request,
}) => {
  for (const [kind, text] of [
    ["tool_call", 'get_claim({"claim_id": "CLM-1003"})'],
    ["reply", "Declined under section 7."],
  ]) {
    await request.post("/api/claims/CLM-1003/steps", { data: { kind, text } });
  }
  await page.goto("/#/claims/CLM-1003");
  const steps = page.getByRole("list", { name: "Agent steps" });
  await expect(steps.getByRole("listitem")).toHaveCount(2);
  await expect(steps).toContainText("Declined under section 7.");

  await request.post("/api/claims/CLM-1003/decision", {
    data: {
      decision: "decline",
      payout: 0,
      reason: "The treatment could have waited until the customer was home.",
      policy_section: "Section 7, Emergency Medical",
    },
  });
  await page.reload();
  await expect(page.locator(".chip")).toHaveText("Declined");
  await expect(
    page.getByText(
      "The treatment could have waited until the customer was home.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Policy wording: Section 7, Emergency Medical"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Run agent" })).toBeHidden();
});

test("a payout over $1,000 waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await request.post("/api/claims/CLM-1011/decision", {
    data: {
      decision: "approve",
      payout: 1250,
      reason: "The airline lost the suitcase. The items are covered.",
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  const payment = await request.post("/api/claims/CLM-1011/payment", {
    data: { amount: 1250 },
  });
  expect(payment.status()).toBe(409);

  await page.goto("/#/claims/CLM-1011");
  await expect(page.locator(".actions .badge")).toHaveText(
    "Waiting for sign-off",
  );
  await expect(
    page.getByText("The payment waits for a handler's sign-off."),
  ).toBeVisible();
  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(
    page.getByText("Paid $1,250.00 after sign-off by Dana Whitfield"),
  ).toBeVisible();
  await expect(page.locator(".actions .badge")).toHaveText("Decided");
});

test("the agent's instructions are read only", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(page.getByText("You are the UnderCover Agent.")).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
