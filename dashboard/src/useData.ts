import { useCallback, useEffect, useState } from "react";

export const REFRESH_MS = 2000;

export interface Loaded<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

export function useData<T>(
  load: () => Promise<T>,
  refreshMs: number | null = null,
): Loaded<T> {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    let live = true;
    const fetchNow = () => {
      load()
        .then((data) => {
          if (live) setState({ data });
        })
        .catch((error: unknown) => {
          if (live) setState((prev) => ({ ...prev, error: String(error) }));
        });
    };
    fetchNow();
    const timer =
      refreshMs === null ? undefined : setInterval(fetchNow, refreshMs);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [load, refreshMs, version]);

  return { data: state.data, error: state.error, reload };
}
