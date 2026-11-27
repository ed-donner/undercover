import { defineConfig } from "@playwright/test";

// Playwright clears outputDir before starting the servers, so each run's
// backend starts from a fresh database seeded from data/.
export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command: "uv run -m uvicorn backend.main:app --port 8001",
      url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false,
      env: { UNDERCOVER_DB: "e2e/test-results/e2e.db" },
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      reuseExistingServer: false,
      env: { BACKEND_PORT: "8001" },
    },
  ],
});
