import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// The tests run on their own ports with a freshly seeded database, so they
// never touch the queue in `npm run dev`.
const database = join(tmpdir(), "undercover-e2e.db");

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command:
        "uv run -m backend.seed && uv run -m uvicorn backend.main:app --port 8001",
      env: { UNDERCOVER_DB: database },
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      env: { BACKEND_URL: "http://127.0.0.1:8001" },
      url: "http://localhost:5174",
      reuseExistingServer: false,
    },
  ],
});
