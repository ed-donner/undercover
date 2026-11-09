import { afterEach, expect, it, vi } from "vitest";
import { fetchClaim, fetchClaims, fetchCurrentRun } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("rejects instead of returning an error body as data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response('{"detail":"No claim"}', { status: 404 })),
    ),
  );

  await expect(fetchClaim("CLM-9999")).rejects.toThrow("404");
});

it("treats a null current run as no run yet", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response("null"))),
  );

  expect(await fetchCurrentRun()).toBeNull();
});

it("reads wire amounts as whole cents", async () => {
  const summary = { claim_id: "CLM-1001", amount_claimed: "1234.50" };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify([summary])))),
  );

  const [claim] = await fetchClaims();

  expect(claim.amount_claimed).toBe(123450);
});
