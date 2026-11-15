import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimPage } from "./ClaimPage";
import { claim, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const waiting = {
  ...claim,
  status: "awaiting_signoff",
  payout: 1250,
  paid: null,
};

it("signs off and pays a payout over the limit", async () => {
  const fetchMock = stubApi({
    "/api/claims/CLM-1001": waiting,
    "/api/handlers": [{ handler_id: "HND-01", name: "Dana Whitfield" }],
    "/api/claims/CLM-1001/sign-off": {},
    "/api/claims/CLM-1001/payment": {},
  });
  render(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: /Sign off and pay \$1,250.00/,
  });
  await waitFor(() => {
    expect(button.hasAttribute("disabled")).toBe(false);
  });
  fireEvent.click(button);
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/claims/CLM-1001/payment",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

it("says when a claim is not decided or read yet", async () => {
  stubApi({
    "/api/claims/CLM-1001": { ...claim, decision: null, steps: [] },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Not decided yet.")).toBeDefined();
  expect(screen.getByText("Nothing yet.")).toBeDefined();
});
