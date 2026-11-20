import { expect, it } from "vitest";

const sources = import.meta.glob<string>("./*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
});

it("keeps backend transport and route strings out of view components", () => {
  for (const [path, source] of Object.entries(sources)) {
    if (/\.test\.tsx?$/.test(path) || path === "./api.ts") continue;
    expect(source, path).not.toMatch(/\bfetch\s*\(/);
    expect(source, path).not.toMatch(
      /import\s*\{[^}]*\b(?:api|post)\b[^}]*\}\s*from\s*["']\.\/api["']/,
    );
    expect(source, path).not.toMatch(
      /["'`]\/(?:api|claims|policies|plans|customers|handlers|agent-runs|documents|instructions|wording)(?:[/"'`])/,
    );
  }
});
