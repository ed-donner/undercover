import { useCallback, useEffect, useState } from "react";
import { errorText } from "./format";

const REFRESH_MS = 2000;

export function useHash(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
    };
  }, []);
  return hash;
}

/** Load data, and keep reloading every two seconds while keepFresh says so. */
export function useData<T>(
  load: () => Promise<T>,
  keepFresh: (data: T) => boolean,
) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [round, setRound] = useState(0);
  const reload = useCallback(() => {
    setRound((count) => count + 1);
  }, []);

  useEffect(() => {
    let current = true;
    load()
      .then((value) => {
        if (current) {
          setData(value);
          setError(undefined);
        }
      })
      .catch((problem: unknown) => {
        if (current) setError(errorText(problem));
      });
    return () => {
      current = false;
    };
  }, [load, round]);

  useEffect(() => {
    if (data === undefined || !keepFresh(data)) return;
    const timer = setTimeout(reload, REFRESH_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [data, keepFresh, reload]);

  return { data, error, reload };
}
