import { expect, test } from "@playwright/test";

test("a claim page shows the claim, its policy and its customer in full", async ({
  page,
}) => {
  await page.goto("/#/claims/CLM-1001");
  const claim = page.getByRole("region", { name: "Claim", exact: true });
  await expect(
    claim.getByText("My flight home from Rome on June 18"),
  ).toBeVisible();
  await expect(claim.getByRole("row")).toHaveCount(4);
  await expect(claim.getByRole("row", { name: "Total $420.00" })).toBeVisible();
  await expect(claim.getByRole("article")).toHaveCount(4);
  await expect(
    page
      .getByRole("region", { name: "Policy" })
      .getByText("UnderCover Premium"),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Customer" }).getByText("CLM-0412"),
  ).toBeVisible();
});

test("the agent's steps appear on the claim page as it works", async ({
  page,
  request,
}) => {
  await page.goto("/#/claims/CLM-1013");
  const steps = page.getByRole("region", { name: "The agent's steps" });
  await expect(steps.getByText("No steps yet.")).toBeVisible();
  expect((await request.post("/api/claims/CLM-1013/start")).ok()).toBe(true);
  const step = await request.post("/api/claims/CLM-1013/steps", {
    data: {
      thread_id: "e2e",
      kind: "tool_call",
      name: "get_policy_wording",
      content: "{}",
    },
  });
  expect(step.ok()).toBe(true);
  await expect(steps.getByText("Reading the policy wording")).toBeVisible();
  await expect(
    page.getByText("The agent is working on this claim."),
  ).toBeVisible();
});

test("a claim the agent failed on twice is left for a handler", async ({
  page,
  request,
}) => {
  for (const attempt of ["first", "second"]) {
    expect((await request.post("/api/claims/CLM-1020/start")).ok()).toBe(true);
    await request.post("/api/claims/CLM-1020/steps", {
      data: {
        thread_id: attempt,
        kind: "failure",
        name: "harness",
        content: `This attempt failed: the ${attempt} try timed out.`,
      },
    });
    expect((await request.post("/api/claims/CLM-1020/release")).ok()).toBe(
      true,
    );
  }
  await page.goto("/#/claims/CLM-1020");
  await expect(
    page.getByText(
      "The agent couldn't finish this claim in two attempts, so it's left for a handler.",
      { exact: false },
    ),
  ).toBeVisible();
  const steps = page.getByRole("region", { name: "The agent's steps" });
  await expect(steps.getByText("Failed")).toHaveCount(2);
  await expect(steps.getByRole("heading", { name: "Attempt 2" })).toBeVisible();
  await page.getByRole("link", { name: "Back to the queue" }).click();
  await expect(
    page.getByRole("row", { name: /CLM-1020/ }).getByText("Left for a handler"),
  ).toBeVisible();
});

test("a claim page lists the sections the agent read", async ({
  page,
  request,
}) => {
  await request.post("/api/claims/CLM-1021/steps", {
    data: {
      thread_id: "e2e",
      kind: "tool_call",
      name: "read_section",
      content: '{"document": "claims_manual", "section": 9}',
    },
  });
  await page.goto("/#/claims/CLM-1021");
  await expect(
    page
      .getByRole("region", { name: "What the agent read" })
      .getByText("Claims manual, section 9: Repeat claims"),
  ).toBeVisible();
});
