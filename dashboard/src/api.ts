import { useEffect, useState } from "react";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body: unknown = await response.json();
    const detail =
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${String(response.status)}).`;
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function post(path: string, body: object = {}): Promise<unknown> {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function useResource<T>(load: () => Promise<T>, interval = 1500) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    let pending = false;
    async function refresh() {
      if (pending) return;
      pending = true;
      try {
        const result = await load();
        if (active) {
          setData(result);
          setError(undefined);
        }
      } catch (cause) {
        if (active) {
          setError(
            cause instanceof Error ? cause.message : "Connection failed.",
          );
        }
      } finally {
        pending = false;
      }
    }
    void refresh();
    const timer = setInterval(() => void refresh(), interval);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [load, interval, version]);

  return {
    data,
    error,
    reload: () => {
      setVersion((current) => current + 1);
    },
  };
}
