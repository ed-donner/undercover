import { expect, test } from "@playwright/test";

const backend = "http://127.0.0.1:8011";

test.beforeEach(async ({ request }) => {
  expect((await request.post(`${backend}/__test__/reset`)).ok()).toBe(true);
});

test("works five claims, repairs an omitted task and leaves twenty untouched", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });
  await page.goto("/");
  await expect(page.getByLabel("Claim cap")).toHaveValue("5");
  await page.getByRole("button", { name: "Start capped run" }).click();
  await expect(page.getByText("Agent working the queue")).toBeVisible();
  const tasks = page.getByRole("list", { name: "Run to-do list" });
  await expect(tasks.locator("li")).toHaveCount(4);
  await expect(tasks.getByText("In progress", { exact: true })).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Start queue" }),
  ).toBeDisabled();
  const conflict = await request.post(`${backend}/api/agent-runs`, {
    data: { mode: "claim", claim_id: "CLM-1007" },
  });
  expect(conflict.status()).toBe(409);
  await request.post(`${backend}/__test__/release`);
  await expect(page.getByText("Run completed", { exact: true })).toBeVisible({
    timeout: 20000,
  });
  await expect(tasks.locator("li")).toHaveCount(5);
  await expect(
    tasks.locator('[data-task-state="todo"], [data-task-state="in_progress"]'),
  ).toHaveCount(0);
  await expect(
    page.getByText(/5 claims worked: 2 done, 3 left for a handler/),
  ).toBeVisible();
  const result = (await (
    await request.get(`${backend}/api/agent-runs`)
  ).json()) as {
    tasks: { claim_id: string; state: string }[];
    checked: boolean;
    status: string;
  }[];
  expect(result[0].tasks.map((task) => task.claim_id)).toEqual([
    "CLM-1005",
    "CLM-1004",
    "CLM-1003",
    "CLM-1002",
    "CLM-1001",
  ]);
  expect(result[0].checked).toBe(true);
  const claims = (await (
    await request.get(`${backend}/api/claims`)
  ).json()) as { claim_id: string; status: string }[];
  expect(claims.filter((claim) => claim.status === "waiting")).toHaveLength(20);
  for (const claim of claims.filter((claim) => claim.status === "waiting")) {
    expect(
      await (
        await request.get(`${backend}/api/claims/${claim.claim_id}/runs`)
      ).json(),
    ).toEqual([]);
  }
  await tasks.getByRole("button", { name: "Review CLM-1001" }).click();
  await expect(
    page.getByText("Simulated payment recorded: $420.00"),
  ).toBeVisible();
  const sources = page.getByRole("region", { name: "Sources read" });
  await sources.getByText(/Claims manual 2026.2 · 9. Repeat claims/).click();
  await expect(
    sources.getByText(/Count claims by the date they were filed/),
  ).toBeVisible();
  await expect(
    page.getByText(/Claims manual 2026.2, sections 4, 9/),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("Run completed", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Run to-do list" }).locator("li"),
  ).toHaveCount(5);
  expect(errors).toEqual([]);
});

test("two technical failures leave an undecided claim for a handler", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .locator(".queue-list")
    .getByRole("button", { name: /CLM-1006/ })
    .click();
  await page.getByRole("button", { name: /Process claim/ }).click();
  await request.post(`${backend}/__test__/release`);
  await expect(
    page.getByText(/Left for a handler: Two attempts failed/),
  ).toBeVisible({ timeout: 15000 });
  await expect(
    page.getByRole("button", { name: /Process claim|Retry claim/ }),
  ).toHaveCount(0);
  await expect(page.getByText("No decision yet.")).toBeVisible();
  const claim = (await (
    await request.get(`${backend}/api/claims/CLM-1006`)
  ).json()) as {
    decision: unknown;
    payment: unknown;
    failures: number;
    needs_handler: boolean;
    status: string;
  };
  expect(claim).toMatchObject({
    decision: null,
    payment: null,
    failures: 2,
    needs_handler: true,
    status: "waiting",
  });
  const restart = await request.post(`${backend}/api/agent-runs`, {
    data: { mode: "claim", claim_id: "CLM-1006" },
  });
  expect(restart.status()).toBe(409);
  await page.reload();
  await page
    .locator(".queue-list")
    .getByRole("button", { name: /CLM-1006/ })
    .click();
  await expect(
    page.getByText(/Left for a handler: Two attempts failed/),
  ).toBeVisible();
});

for (const colorScheme of ["light", "dark"] as const) {
  test(`queue tasks and sources fit narrow ${colorScheme} screens`, async ({
    page,
    request,
  }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ colorScheme });
    await page.goto("/");
    await page.getByRole("button", { name: "Start capped run" }).click();
    await request.post(`${backend}/__test__/release`);
    await expect(page.getByText("Run completed", { exact: true })).toBeVisible({
      timeout: 20000,
    });
    await page.getByRole("button", { name: "Review CLM-1001" }).click();
    const sources = page.getByRole("region", { name: "Sources read" });
    await sources.getByText(/Policy wording 2026.1 · 3. Trip Delay/).click();
    await expect(
      sources.getByText(/We pay when your carrier delays you/),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`harness-${colorScheme}.png`),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Agent instructions" }).click();
    await expect(
      page.getByRole("heading", { name: "Queue instructions", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", {
        name: /Manual 2026.2 · 10. Meals without receipts/,
      })
      .click();
    await expect(
      page.getByText(/Customers stuck at an airport often pay cash/),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
}
