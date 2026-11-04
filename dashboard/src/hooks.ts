import { useEffect, useState } from "react";

export const POLL_MS = 2000;

export interface Loaded<T> {
  data: T | undefined;
  failed: boolean;
  reload: () => void;
}

/** Load from the API, and again every pollMs if given. `load` must be stable. */
export function useApi<T>(load: () => Promise<T>, pollMs?: number): Loaded<T> {
  const [data, setData] = useState<T>();
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let active = true;
    const refresh = () => {
      load().then(
        (value) => {
          if (!active) return;
          setData(value);
          setFailed(false);
        },
        () => {
          if (active) setFailed(true);
        },
      );
    };
    refresh();
    const timer =
      pollMs === undefined ? undefined : window.setInterval(refresh, pollMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [load, pollMs, version]);

  return {
    data,
    failed,
    reload: () => {
      setVersion((current) => current + 1);
    },
  };
}

export function useHash(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", update);
    return () => {
      window.removeEventListener("hashchange", update);
    };
  }, []);
  return hash;
}
