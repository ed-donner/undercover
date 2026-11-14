import { useEffect, useState } from "react";
import { api, message } from "./api";

interface Loaded<T> {
  path: string;
  data?: T;
  error?: string;
}

export function useGet<T>(path: string) {
  const [loaded, setLoaded] = useState<Loaded<T>>({ path });

  useEffect(() => {
    let live = true;
    api.get<T>(path).then(
      (data) => {
        if (live) setLoaded({ path, data });
      },
      (error: unknown) => {
        if (live) setLoaded({ path, error: message(error) });
      },
    );
    return () => {
      live = false;
    };
  }, [path]);

  return loaded.path === path ? loaded : { path };
}
