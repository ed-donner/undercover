import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  globalSetup: "./e2e/globalSetup.ts",
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
      env: { UNDERCOVER_AGENT: "http://127.0.0.1:8003", DATABASE_URL: "" },
    },
    {
      command: "npx vite dashboard --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
    },
  ],
});
