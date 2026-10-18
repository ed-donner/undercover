import { useEffect, useState } from "react";

interface Polled<T> {
  data?: T;
  error?: string;
}

/** Load, then again every `interval` ms (never, if null) until `done` says the data is final. `load` and `done` must be stable. */
export function usePolled<T>(
  load: () => Promise<T>,
  interval: number | null,
  done?: (data: T) => boolean,
) {
  const [state, setState] = useState<Polled<T>>({});
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let current = true;
    const timer =
      interval === null ? undefined : setInterval(refresh, interval);
    function refresh() {
      load()
        .then((data) => {
          if (!current) return;
          setState({ data });
          if (done?.(data)) clearInterval(timer);
        })
        .catch((error: unknown) => {
          if (current)
            setState((previous) => ({ ...previous, error: String(error) }));
        });
    }
    refresh();
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [load, interval, done, reloads]);

  return {
    ...state,
    reload: () => {
      setReloads((count) => count + 1);
    },
  };
}
