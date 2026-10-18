import { useEffect, useState } from "react";

interface Polled<T> {
  data?: T;
  error?: string;
}

/** Load once, then again every `interval` ms while `active`. `load` must be stable. */
export function usePolled<T>(
  load: () => Promise<T>,
  interval: number,
  active = true,
) {
  const [state, setState] = useState<Polled<T>>({});
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let current = true;
    const refresh = () => {
      load()
        .then((data) => {
          if (current) setState({ data });
        })
        .catch((error: unknown) => {
          if (current)
            setState((previous) => ({ ...previous, error: String(error) }));
        });
    };
    refresh();
    const timer = active ? setInterval(refresh, interval) : undefined;
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [load, interval, active, reloads]);

  return {
    ...state,
    reload: () => {
      setReloads((count) => count + 1);
    },
  };
}
