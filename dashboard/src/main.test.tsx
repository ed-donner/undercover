import { screen } from "@testing-library/react";
import { expect, it } from "vitest";

it("renders the app into #root", async () => {
  document.body.innerHTML = '<div id="root"></div>';

  await import("./main");

  expect(await screen.findByRole("navigation")).toBeDefined();
});
