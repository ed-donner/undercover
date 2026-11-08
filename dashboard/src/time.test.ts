import { expect, it } from "vitest";
import { formatTime } from "./time";

it("formats a timestamp with its date and time", () => {
  const text = formatTime("2026-06-03T14:30:00+00:00");

  expect(text).toContain("2026");
  expect(text).toMatch(/\d{1,2}:\d{2}/);
});
