import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { fixture } from "../test-fixtures";
import { App } from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("loads the full workspace and searchable queue", async () => {
  fixture();
  render(<App />);
  expect(screen.getByText("Loading queue…")).toBeDefined();
  expect(
    await screen.findByRole("heading", { name: "Maya Patel", level: 2 }),
  ).toBeDefined();
  expect(screen.getByText(/My flight was canceled/)).toBeDefined();
  expect(screen.getByText("Hotel paid: $420.00.")).toBeDefined();
  expect(screen.getByText("Bag arrived late")).toBeDefined();
  expect(screen.getByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("6 hours")).toBeDefined();
  expect(screen.getAllByText("$420.00").length).toBeGreaterThan(1);
  fireEvent.change(screen.getByLabelText("Search claims"), {
    target: { value: "absent" },
  });
  expect(screen.getByText("No matching claims.")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Search claims"), {
    target: { value: "Maya" },
  });
  fireEvent.change(screen.getByLabelText("Filter by status"), {
    target: { value: "decided" },
  });
  expect(screen.getByText("No matching claims.")).toBeDefined();
  fireEvent.change(screen.getByLabelText("Filter by status"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByRole("button", { name: /CLM-1001/ }));
  expect(
    screen
      .getByRole("button", { name: /CLM-1001/ })
      .getAttribute("aria-pressed"),
  ).toBe("true");
});

it("selects another claim without showing stale details", async () => {
  const data = fixture();
  data.queue.push({
    ...data.queue[0],
    claim_id: "CLM-1002",
    customer_name: "Tom Becker",
  });
  data.responses.set("/api/claims/CLM-1002", {
    ...data.claim,
    claim_id: "CLM-1002",
    customer_id: "CUS-3002",
  });
  data.responses.set("/api/customers/CUS-3002", {
    ...data.customer,
    name: "Tom Becker",
    customer_id: "CUS-3002",
    previous_claims: [],
  });
  data.responses.set("/api/claims/CLM-1002/runs", []);
  data.responses.set("/api/claims/CLM-1002/events", []);
  data.responses.set("/api/claims/CLM-1002/reads", []);
  render(<App />);
  await screen.findByRole("heading", { name: "Maya Patel", level: 2 });
  fireEvent.click(screen.getByRole("button", { name: /CLM-1002/ }));
  expect(
    await screen.findByRole("heading", { name: "Tom Becker", level: 2 }),
  ).toBeDefined();
  expect(screen.getByText("No previous claims.")).toBeDefined();
  expect(
    screen.queryByRole("heading", { name: "Maya Patel", level: 2 }),
  ).toBeNull();
});

it("shows an empty queue", async () => {
  fixture().responses.set("/api/claims", []);
  render(<App />);
  expect(await screen.findByText("No claims in the queue.")).toBeDefined();
  expect(
    screen.getByText("Select a claim to review its evidence."),
  ).toBeDefined();
});

it("recovers from a queue connection error", async () => {
  const data = fixture();
  data.fetcher.mockRejectedValueOnce(new Error("Backend offline"));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Backend offline Retry queue",
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry queue" }));
  expect(
    await screen.findByRole("heading", { name: "Maya Patel", level: 2 }),
  ).toBeDefined();
});

it("displays instructions and wording without edit controls", async () => {
  fixture();
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Agent instructions" }));
  expect(
    await screen.findByText("Read the wording and manual. Record a decision."),
  ).toBeDefined();
  expect(screen.getByText(/Receipts are required/)).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Claims queue/ }));
  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Maya Patel", level: 2 }),
    ).toBeDefined();
  });
});
