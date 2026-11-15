import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";

export interface Fetched<T> {
  data: T | null;
  reload: () => void;
}

export function useFetch<T>(path: string, pollMs = 0): Fetched<T> {
  const [data, setData] = useState<T | null>(null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => {
    setTick((n) => n + 1);
  }, []);

  useEffect(() => {
    let live = true;
    const load = () => {
      void getJson<T>(path)
        .then((value) => {
          if (live) setData(value);
        })
        .catch(() => {
          if (live) setData(null);
        });
    };
    load();
    if (pollMs === 0) {
      return () => {
        live = false;
      };
    }
    const timer = setInterval(load, pollMs);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [path, pollMs, tick]);

  return { data, reload };
}
