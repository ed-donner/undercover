import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { parseRoute } from "./hooks";
import { claim, mockApi, policy, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

describe("parseRoute", () => {
  it("reads each page from the hash", () => {
    expect(parseRoute("")).toEqual({ page: "queue" });
    expect(parseRoute("#/")).toEqual({ page: "queue" });
    expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
    expect(parseRoute("#/claims/CLM-1001")).toEqual({
      page: "claim",
      claimId: "CLM-1001",
    });
    expect(parseRoute("#/elsewhere")).toEqual({ page: "queue" });
  });
});

describe("App", () => {
  it("shows the queue by default", async () => {
    mockApi({ "GET /api/claims": [summary()] });
    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "Claims queue" }),
    ).toBeDefined();
  });

  it("shows the instructions page", async () => {
    mockApi({ "GET /api/instructions": { text: "Decide claims." } });
    window.location.hash = "#/instructions";
    render(<App />);
    expect(await screen.findByText("Decide claims.")).toBeDefined();
  });

  it("shows a claim page and follows the hash", async () => {
    mockApi({
      "GET /api/claims": [summary()],
      "GET /api/claims/CLM-1001": claim(),
      "GET /api/claims/CLM-1001/steps": [],
      "GET /api/policies/POL-2001": policy,
      "GET /api/handlers": [],
    });
    render(<App />);
    await screen.findByRole("heading", { name: "Claims queue" });
    act(() => {
      window.location.hash = "#/claims/CLM-1001";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(
      await screen.findByRole("heading", { name: /CLM-1001/ }),
    ).toBeDefined();
  });
});
