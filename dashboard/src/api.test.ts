import { afterEach, expect, it, vi } from "vitest";
import {
  getClaim,
  getInstructions,
  signOffClaim,
  startClaimRun,
  startQueueRun,
} from "./api";
import { idle, Refusal, stubApi } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("reads instructions as text", async () => {
  stubApi({ "GET /api/instructions": { text: "Be careful." } });
  expect(await getInstructions()).toBe("Be careful.");
});

it("throws the backend's reason when it refuses", async () => {
  stubApi({ "GET /api/claims/CLM-1001": new Refusal("Not today") });
  await expect(getClaim("CLM-1001")).rejects.toThrow("Not today");
});

it("posts runs and sign-offs", async () => {
  const calls = stubApi({
    "POST /api/claims/CLM-1001/run": idle,
    "POST /api/runs": idle,
    "POST /api/claims/CLM-1001/sign-off": { amount: 1500 },
  });
  await startClaimRun("CLM-1001");
  await startQueueRun();
  await signOffClaim("CLM-1001", "HND-01");
  expect(calls.map((call) => call.key)).toEqual([
    "POST /api/claims/CLM-1001/run",
    "POST /api/runs",
    "POST /api/claims/CLM-1001/sign-off",
  ]);
  expect(calls[2]?.body).toEqual({ handler_id: "HND-01" });
});
