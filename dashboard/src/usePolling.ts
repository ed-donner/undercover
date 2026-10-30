import { useEffect } from "react";

/** Call `load` every two seconds while `active` is true. */
export function usePolling(load: () => void, active: boolean) {
  useEffect(() => {
    if (!active) return;
    const interval = setInterval(load, 2000);
    return () => {
      clearInterval(interval);
    };
  }, [load, active]);
}
