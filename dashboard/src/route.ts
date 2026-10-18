import { useSyncExternalStore } from "react";

export type Route = { name: "queue" } | { name: "unknown" };

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, "");
  if (path === "" || path === "/") return { name: "queue" };
  return { name: "unknown" };
}

function subscribe(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
  };
}

const currentHash = () => window.location.hash;

export function useRoute(): Route {
  return parseRoute(useSyncExternalStore(subscribe, currentHash));
}
