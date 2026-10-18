import { vi } from "vitest";

type Routes = Record<string, unknown>;

/** Replace fetch with canned JSON replies keyed by "METHOD /path". A function reply is called each time; anything else is a 404. */
export function mockApi(routes: Routes) {
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${input}`;
    if (!(key in routes))
      return Promise.resolve(new Response("{}", { status: 404 }));
    const reply = routes[key];
    return Promise.resolve(
      Response.json(
        typeof reply === "function" ? (reply as () => unknown)() : reply,
      ),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
