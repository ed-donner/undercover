import { afterEach, expect, it, vi } from "vitest";
import { fetchClaim, fetchCurrentRun } from "./api";
import { formatMoney } from "./money";

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

it("formats money in dollars with separators", () => {
  expect(formatMoney(1234.5)).toBe("$1,234.50");
});
