import { vi } from "vitest";

type Routes = Record<string, unknown>;

/** Replace fetch with canned JSON replies keyed by "METHOD /path"; anything else is a 404. */
export function mockApi(routes: Routes) {
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${input}`;
    if (!(key in routes))
      return Promise.resolve(new Response("{}", { status: 404 }));
    return Promise.resolve(Response.json(routes[key]));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
