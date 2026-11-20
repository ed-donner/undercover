import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5174",
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "uv run -m e2e.server",
      url: "http://127.0.0.1:8011/api/health",
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --host 127.0.0.1 --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      env: { VITE_BACKEND_URL: "http://127.0.0.1:8011" },
      reuseExistingServer: false,
    },
  ],
});
