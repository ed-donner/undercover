import { useEffect, useState } from "react";

const POLL_MS = 2000;

/**
 * Call `load` now, and every two seconds while `active` is true.
 * Returns whether the latest call failed.
 */
export function usePolling(
  load: () => Promise<unknown>,
  active: boolean,
): boolean {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const run = () => {
      load().then(
        () => {
          setFailed(false);
        },
        () => {
          setFailed(true);
        },
      );
    };
    run();
    if (!active) return;
    const interval = setInterval(run, POLL_MS);
    return () => {
      clearInterval(interval);
    };
  }, [load, active]);

  return failed;
}
