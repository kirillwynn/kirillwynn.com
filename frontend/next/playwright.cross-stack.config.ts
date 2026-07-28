import { defineConfig } from "@playwright/test";

const djangoEnvironment = {
    CROSS_STACK_STATE_FILE: "/tmp/kirillwynn-cross-stack-state.json",
    DJANGO_SETTINGS_MODULE: "config.settings.cross_stack",
    DJANGO_TEST_DATABASE: "/tmp/kirillwynn-cross-stack.sqlite3",
};

export default defineConfig({
    testDir: "./e2e/cross-stack",
    timeout: 60_000,
    fullyParallel: false,
    workers: 1,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI
        ? [
              ["line"],
              [
                  "html",
                  {
                      open: "never",
                      outputFolder: "playwright-report/cross-stack",
                  },
              ],
          ]
        : "line",
    use: {
        baseURL: "http://localhost:3200",
        browserName: "chromium",
        viewport: { width: 1440, height: 900 },
        screenshot: "only-on-failure",
        trace: "retain-on-failure",
        video: "off",
    },
    outputDir: "test-results/cross-stack",
    webServer: [
        {
            command: "node e2e/cross-stack/mock-providers.mjs",
            url: "http://127.0.0.1:3202/__health",
            reuseExistingServer: !process.env.CI,
            timeout: 30_000,
        },
        {
            command: "sh tests/e2e/run_cross_stack_server.sh",
            cwd: "../../backend/django",
            url: "http://127.0.0.1:3201/api/health/",
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
            env: djangoEnvironment,
        },
        {
            command: "npm run dev -- --hostname 127.0.0.1 --port 3200",
            url: "http://127.0.0.1:3200",
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
            env: {
                DJANGO_API_URL: "http://127.0.0.1:3201",
                PREVIEW_COOKIE_SECURE: "false",
                PREVIEW_TOKEN_TTL_SECONDS: "600",
                PUBLIC_SITE_URL: "http://localhost:3200",
            },
        },
    ],
});
