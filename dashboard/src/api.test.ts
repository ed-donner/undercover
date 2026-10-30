import { afterEach, expect, it, vi } from "vitest";
import { fetchClaim, fetchClaims, fetchCurrentRun, payClaim } from "./api";

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

it("treats a 404 for the current run as no run yet", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(null, { status: 404 }))),
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

it("pays with a wire amount built from whole cents", async () => {
  let sent: unknown;
  vi.stubGlobal("fetch", (path: string, init: RequestInit) => {
    sent = init.body;
    return Promise.resolve(new Response(path));
  });

  await payClaim("CLM-1001", 120005);

  expect(sent).toBe('{"amount":"1200.05"}');
});
