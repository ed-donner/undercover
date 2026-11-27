import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Queue } from "./Queue";
import { mockApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("lists the claims with their state and counts", async () => {
  mockApi({
    "/api/claims": [
      summary,
      { ...summary, claim_id: "CLM-1002", status: "awaiting_signoff" },
    ],
  });
  render(<Queue />);
  const link = await screen.findByRole("link", { name: "CLM-1001" });
  expect(link.getAttribute("href")).toBe("#/claims/CLM-1001");
  const rows = screen.getAllByRole("row");
  expect(rows).toHaveLength(3);
  expect(within(rows[1]).getByText("$420.00")).toBeDefined();
  expect(within(rows[1]).getByText("Trip delay")).toBeDefined();
  expect(within(rows[1]).getByText("Jun 24, 2026")).toBeDefined();
  expect(within(rows[2]).getByText("Waiting for sign-off")).toBeDefined();
  const tiles = within(screen.getByLabelText("Claims by state"));
  expect(tiles.getAllByText("1")).toHaveLength(2);
  expect(tiles.getAllByText("0")).toHaveLength(2);
});

it("shows an error when the backend is down", async () => {
  mockApi({ "/api/claims": new Error("offline") });
  render(<Queue />);
  expect((await screen.findByRole("alert")).textContent).toBe("offline");
});
