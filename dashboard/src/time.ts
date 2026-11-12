/** Format a wire timestamp for people, in the viewer's own time zone. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
