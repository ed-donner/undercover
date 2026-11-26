import { useEffect, useState } from "react";

export interface Loaded<T> {
  data: T | undefined;
  error: string | undefined;
}

export function useData<T>(load: () => Promise<T>): Loaded<T> {
  const [state, setState] = useState<Loaded<T>>({
    data: undefined,
    error: undefined,
  });

  useEffect(() => {
    let live = true;
    load()
      .then((data) => {
        if (live) setState({ data, error: undefined });
      })
      .catch((error: unknown) => {
        if (live) setState({ data: undefined, error: String(error) });
      });
    return () => {
      live = false;
    };
  }, [load]);

  return state;
}
