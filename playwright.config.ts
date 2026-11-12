import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { defineConfig } from "@playwright/test";

/** A fresh database for each run, so the backend never holds a deleted file. */
const databasePath = path.join(
  mkdtempSync(path.join(tmpdir(), "undercover-e2e-")),
  "test.db",
);

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: "node e2e/agentStandIn.mjs",
      url: "http://127.0.0.1:8003/calls",
    },
    {
      command: "uv run -m uvicorn backend.main:app --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      env: {
        UNDERCOVER_AGENT: "http://127.0.0.1:8003",
        DATABASE_URL: "",
        DATABASE_PATH: databasePath,
      },
    },
    {
      command: "npx vite dashboard --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
    },
  ],
});
