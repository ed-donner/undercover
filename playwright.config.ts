import { defineConfig } from "@playwright/test";
import path from "node:path";

const BACKEND = "http://127.0.0.1:8100";
const E2E_DB = path.resolve("backend", "e2e.db");

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command:
        "uv run -m backend.reset && uv run -m uvicorn backend.main:app --port 8100",
      url: `${BACKEND}/api/health`,
      env: { UNDERCOVER_DB: E2E_DB },
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      env: { BACKEND_URL: BACKEND },
    },
  ],
});
