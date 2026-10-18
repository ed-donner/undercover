import { rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "@playwright/test";

// The tests run their own servers on their own ports, on a new database,
// so a test run never touches the queue that `npm run dev` uses.
const database = join(tmpdir(), "undercover-e2e.db");
if (!process.env.TEST_WORKER_INDEX) rmSync(database, { force: true });

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: "http://localhost:5273" },
  webServer: [
    {
      command: "uv run -m uvicorn backend.main:app --port 8100",
      url: "http://127.0.0.1:8100/api/health",
      env: { UNDERCOVER_DB: database },
    },
    {
      command: "npx vite dashboard --port 5273 --strictPort",
      url: "http://localhost:5273",
      env: { BACKEND_URL: "http://127.0.0.1:8100" },
    },
  ],
});
