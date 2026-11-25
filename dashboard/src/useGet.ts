import { useCallback, useEffect, useState } from "react";
import { api, message } from "./api";

interface Loaded<T> {
  path: string;
  data?: T;
  error?: string;
}

export function useGet<T>(
  path: string,
  everyMs = 0,
): Loaded<T> & { reload: () => void } {
  const [loaded, setLoaded] = useState<Loaded<T>>({ path });
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    let live = true;
    const load = () => {
      void api.get<T>(path).then(
        (data) => {
          if (live) setLoaded({ path, data });
        },
        (error: unknown) => {
          if (live) setLoaded((last) => ({ ...last, error: message(error) }));
        },
      );
    };
    load();
    const timer = everyMs > 0 ? setInterval(load, everyMs) : undefined;
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [path, everyMs, version]);

  return { ...(loaded.path === path ? loaded : { path }), reload };
}
