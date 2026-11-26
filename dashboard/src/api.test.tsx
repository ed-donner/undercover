import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api, claimsApi, documentsApi, runsApi } from "./api";
import { fixture } from "../test-fixtures";
import { useResource } from "./useResource";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("handles non-string API validation details", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({ detail: [] }, { status: 422 })),
  );
  await expect(api("/claims")).rejects.toThrow("Request failed (422).");
});

it("encodes identifiers in named API operations", async () => {
  const data = fixture();
  await claimsApi.signOff("CLM/one ?", "HND-01");
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/claims/CLM%2Fone%20%3F/sign-off",
    expect.objectContaining({ body: '{"handler_id":"HND-01"}' }),
  );
  await documentsApi.section("manual/one", 9);
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/documents/manual%2Fone/sections/9",
    undefined,
  );
  await runsApi.startClaim("CLM/one ?");
  expect(data.fetcher).toHaveBeenCalledWith(
    "/api/agent-runs",
    expect.objectContaining({
      body: '{"mode":"claim","claim_id":"CLM/one ?"}',
    }),
  );
});

it("does not overlap polls or update an unmounted component", async () => {
  vi.useFakeTimers();
  const resolvers: ((value: string) => void)[] = [];
  const load = vi.fn(
    () =>
      new Promise<string>((done) => {
        resolvers.push(done);
      }),
  );
  function Component() {
    const resource = useResource(load, 50);
    return <p>{resource.data ?? "Pending"}</p>;
  }
  const view = render(<Component />);
  await act(() => vi.advanceTimersByTimeAsync(150));
  expect(load).toHaveBeenCalledOnce();
  expect(screen.getByText("Pending")).toBeDefined();
  view.unmount();
  await act(() => {
    resolvers[0]("Finished");
    return Promise.resolve();
  });
  expect(screen.queryByText("Finished")).toBeNull();
});

it("handles a connection rejection", async () => {
  const load = () => Promise.reject(new TypeError("Connection failed."));
  function Component() {
    const resource = useResource(load);
    return <p>{resource.error ?? "Pending"}</p>;
  }
  render(<Component />);
  expect(await screen.findByText("Connection failed.")).toBeDefined();
});
