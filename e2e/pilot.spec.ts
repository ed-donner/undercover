import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const decision = (outcome: string, payout: number, explanation: string) => ({
  decision: outcome,
  payout,
  explanation,
  policy_section: "Section 3, Trip Delay",
});

test("the queue lists every claim, all waiting", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Waiting 25" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Decided 0" })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(26);
});

test("a declined claim shows its reasons and the agent's steps", async ({
  page,
  request,
}) => {
  await request.post("/api/claims/CLM-1001/start");
  await request.post("/api/claims/CLM-1001/steps", {
    data: { kind: "tool_call", text: "get_claim({'claim_id': 'CLM-1001'})" },
  });
  await request.post("/api/claims/CLM-1001/decision", {
    data: decision(
      "decline",
      0,
      "The delay was shorter than the waiting period.",
    ),
  });
  await request.post("/api/claims/CLM-1001/steps", {
    data: { kind: "message", text: "Declined the claim." },
  });
  await page.goto("/#/claims/CLM-1001");
  await expect(page.getByText("Decided", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Declined" })).toBeVisible();
  await expect(
    page.getByText("The delay was shorter than the waiting period."),
  ).toBeVisible();
  await expect(page.getByText("Section 3, Trip Delay")).toBeVisible();
  await expect(page.getByText("Nothing to pay.")).toBeVisible();
  await expect(
    page.getByText("get_claim({'claim_id': 'CLM-1001'})"),
  ).toBeVisible();
  await expect(page.getByText("Declined the claim.")).toBeVisible();
});

test("a small approval is paid straight away", async ({ page, request }) => {
  await request.post("/api/claims/CLM-1002/start");
  await request.post("/api/claims/CLM-1002/decision", {
    data: decision("approve", 200, "The suitcase delay is covered."),
  });
  const payment = await request.post("/api/claims/CLM-1002/payment", {
    data: { amount: 200 },
  });
  expect(payment.ok()).toBe(true);
  await page.goto("/#/claims/CLM-1002");
  await expect(
    page.getByRole("heading", { name: "Approved, $200.00" }),
  ).toBeVisible();
  await expect(page.getByText(/^Paid \$200\.00 on/)).toBeVisible();
  await page.getByRole("link", { name: "Back to the queue" }).click();
  await expect(page.getByRole("row", { name: /CLM-1002/ })).toContainText(
    "Approved, $200.00",
  );
});

test("a large approval is held until a handler signs off", async ({
  page,
  request,
}) => {
  await request.post("/api/claims/CLM-1003/start");
  await request.post("/api/claims/CLM-1003/decision", {
    data: decision("approve", 1250, "The hospital bill is covered."),
  });

  const blocked = await request.post("/api/claims/CLM-1003/payment", {
    data: { amount: 1250 },
  });
  expect(blocked.status()).toBe(409);

  await page.goto("/#/claims/CLM-1003");
  await expect(
    page.getByText("Waiting for sign-off", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("The payment is held until a handler signs off."),
  ).toBeVisible();
  await expect(page.getByText(/^Paid /)).toBeHidden();

  await page.getByLabel("Handler").selectOption({ label: "Dana Whitfield" });
  await page
    .getByRole("button", { name: "Sign off and pay $1,250.00" })
    .click();

  await expect(page.getByText("Decided", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Paid \$1,250\.00 on/)).toBeVisible();
  await expect(page.getByText(/^Dana Whitfield, /)).toBeVisible();
  await expect(page.getByText("Sign-off needed")).toBeHidden();

  await page.goto("/");
  await expect(page.getByRole("row", { name: /CLM-1003/ })).toContainText(
    "Decided",
  );
});

test("the instructions are shown and cannot be edited", async ({ page }) => {
  await page.goto("/#/instructions");
  await expect(
    page.getByRole("heading", { name: "Agent instructions" }),
  ).toBeVisible();
  await expect(
    page.getByText("A payout over $1,000.00 needs a handler's sign-off."),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
