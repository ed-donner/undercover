import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export const POLL_MS = 2000;
export const THEME_KEY = "undercover-theme";

export type Theme = "light" | "dark";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem(THEME_KEY, next);
    setTheme(next);
  }, [theme]);

  return { theme, toggle };
}

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "instructions" };

export function parseRoute(hash: string): Route {
  const claim = /^#\/claims\/([\w-]+)$/.exec(hash);
  if (claim?.[1]) return { page: "claim", claimId: claim[1] };
  if (hash === "#/instructions") return { page: "instructions" };
  return { page: "queue" };
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
  };
}

export function useRoute(): Route {
  return parseRoute(
    useSyncExternalStore(subscribe, () => window.location.hash),
  );
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function useLoad<T>(
  load: () => Promise<T>,
  shouldPoll: (data: T | null) => boolean = () => false,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    load().then(
      (loaded) => {
        setData(loaded);
        setError(null);
      },
      (failure: unknown) => {
        setError(message(failure));
      },
    );
  }, [load]);

  const poll = shouldPoll(data);
  useEffect(() => {
    refresh();
    if (!poll) return;
    const timer = setInterval(refresh, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [refresh, poll]);

  return { data, error, refresh };
}

export function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const act = useCallback(async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(message(failure));
    } finally {
      setBusy(false);
    }
  }, []);

  return { act, busy, error };
}
