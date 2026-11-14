import { expect, test, type APIRequestContext } from "@playwright/test";

const REASON =
  "Meridian Air canceled the flight for a crew problem. The hotel, meals and taxis are covered.";

async function decide(
  request: APIRequestContext,
  claimId: string,
  decision: object,
) {
  expect((await request.post(`/api/claims/${claimId}/start`)).ok()).toBe(true);
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: decision,
  });
  expect(response.ok()).toBe(true);
}

test("the queue shows every claim and the count in each state", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /^CLM-/ })).toHaveCount(25);
  const counts = await Promise.all(
    ["Waiting", "In progress", "Waiting for sign-off", "Decided"].map(
      async (state) =>
        Number(await page.getByLabel(`${state} count`).textContent()),
    ),
  );
  expect(counts.reduce((sum, count) => sum + count, 0)).toBe(25);
});

test("a decision made through the API shows on the claim and the queue", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1001", {
    decision: "approve",
    payout: 420,
    reason: REASON,
    policy_section: "3. Trip Delay",
  });
  await page.goto("/#/claims/CLM-1001");
  const decision = page.getByLabel("Decision");
  await expect(decision.getByText("Approve $420.00")).toBeVisible();
  await expect(decision.getByText(REASON)).toBeVisible();
  await expect(decision.getByText("3. Trip Delay")).toBeVisible();
  await page.getByText("The policy wording for this section").click();
  await expect(decision.getByText("## 3. Trip Delay")).toBeVisible();

  await page.getByRole("link", { name: "Back to the queue" }).click();
  const row = page.getByRole("row", { name: /CLM-1001/ });
  await expect(row.getByText("Decided")).toBeVisible();
});

test("a payout over $1,000 waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1002", {
    decision: "approve",
    payout: 1150,
    reason: "The carrier lost the checked bag on a connecting flight.",
    policy_section: "5. Baggage and Personal Effects",
  });
  const payment = await request.post("/api/claims/CLM-1002/payment", {
    data: { amount: 1150 },
  });
  expect(payment.status()).toBe(409);

  await page.goto("/#/claims/CLM-1002");
  await expect(page.getByText("Waiting for sign-off")).toBeVisible();
  await page.getByLabel("Handler").selectOption({ label: "Dana Whitfield" });
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.getByText("Signed off by Dana Whitfield")).toBeVisible();
  await expect(page.getByText(/^Paid \$1,150\.00 on/)).toBeVisible();
  await expect(page.locator(".claim-title").getByText("Decided")).toBeVisible();
});

test("the instructions view shows the agent's instructions", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Instructions" }).click();
  await expect(
    page.getByText("You are the UnderCover Agent.", { exact: false }),
  ).toBeVisible();
});
