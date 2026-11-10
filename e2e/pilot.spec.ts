import { expect, test } from "@playwright/test";

const backend = "http://127.0.0.1:8011";

test.beforeEach(async ({ request }) => {
  const response = await request.post(`${backend}/__test__/reset`);
  expect(response.ok()).toBe(true);
});

test("shows full records, instructions and a paid below-limit approval", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Maya Patel", level: 2 }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /CLM-10/ })).toHaveCount(25);
  await page.getByText("Hotel receipt", { exact: false }).click();
  await expect(page.getByText(/Guest: Maya Patel/)).toBeVisible();
  await expect(page.getByText("POL-2001", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Process claim/ }).click();
  await expect(page.getByText("Agent working")).toBeVisible();
  await expect(page.getByText("Agent started", { exact: true })).toBeVisible();
  const released = await request.post(`${backend}/__test__/release`);
  expect(released.ok()).toBe(true);
  await expect(
    page.getByText("Simulated payment recorded: $420.00"),
  ).toBeVisible();
  await expect(
    page.getByText("Agent completed", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Policy sections 3, 10/)).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Simulated payment recorded: $420.00"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Agent instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "Agent instructions", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Base coverage decisions on the policy wording alone/),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: /Claims queue/ }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});

test("blocks above-limit payment even through a direct API call", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /CLM-1003/ }).click();
  await page.getByRole("button", { name: /Process claim/ }).click();
  await request.post(`${backend}/__test__/release`);
  await expect(
    page.getByRole("button", { name: "Sign off payout" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Simulated payment blocked by backend rules"),
  ).toBeVisible();
  const blocked = await request.post(`${backend}/api/claims/CLM-1003/payment`, {
    data: { amount: 1200 },
  });
  expect(blocked.status()).toBe(409);
  await expect(page.getByText("No simulated payment recorded.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Record simulated payment" }),
  ).toHaveCount(0);
  await page.getByLabel("Signing handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off payout" }).click();
  await expect(page.getByText("No simulated payment recorded.")).toBeVisible();
  await page.getByRole("button", { name: "Record simulated payment" }).click();
  await expect(
    page.getByText("Simulated payment recorded: $1,200.00"),
  ).toBeVisible();
  const duplicate = await request.post(
    `${backend}/api/claims/CLM-1003/payment`,
    { data: { amount: 1200 } },
  );
  expect(duplicate.status()).toBe(409);
  await page.reload();
  await page.getByRole("button", { name: /CLM-1003/ }).click();
  await expect(
    page.getByText("Simulated payment recorded: $1,200.00"),
  ).toBeVisible();
  await expect(page.getByText("HND-01", { exact: true })).toBeVisible();
});

for (const [claimId, outcome] of [
  ["CLM-1002", "decline"],
  ["CLM-1004", "refer"],
]) {
  test(`records ${outcome} without offering payment`, async ({
    page,
    request,
  }) => {
    await page.goto("/");
    await page.getByRole("button", { name: new RegExp(claimId) }).click();
    await page.getByRole("button", { name: /Process claim/ }).click();
    await request.post(`${backend}/__test__/release`);
    await expect(page.getByText(outcome, { exact: true })).toBeVisible();
    await expect(
      page.getByText("Agent completed", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Record simulated payment" }),
    ).toHaveCount(0);
    await expect(
      page.getByText("No simulated payment recorded."),
    ).toBeVisible();
  });
}

test("retries a failed undecided run and retains the failure history", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /CLM-1005/ }).click();
  await page.getByRole("button", { name: /Process claim/ }).click();
  await request.post(`${backend}/__test__/release`);
  await expect(page.getByRole("button", { name: /Retry claim/ })).toBeVisible();
  await expect(
    page.getByText("Agent run failed", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Retry claim/ }).click();
  await expect(page.getByText("refer", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Agent completed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Agent run failed", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Retry claim/ })).toHaveCount(
    0,
  );
});

for (const colorScheme of ["light", "dark"] as const) {
  test(`fits a narrow ${colorScheme} viewport with readable evidence`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ colorScheme });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Maya Patel", level: 2 }),
    ).toBeVisible();
    await page.getByText("Hotel receipt", { exact: false }).click();
    await expect(page.getByText(/Guest: Maya Patel/)).toBeVisible();
    const fits = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(fits).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`mobile-${colorScheme}.png`),
      fullPage: true,
    });
  });
}
