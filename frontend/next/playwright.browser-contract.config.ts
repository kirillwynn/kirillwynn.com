import { defineConfig } from "@playwright/test";

const viewports = [
    { name: "mobile-375", viewport: { width: 375, height: 812 } },
    { name: "tablet-768", viewport: { width: 768, height: 1024 } },
    { name: "desktop-1440", viewport: { width: 1440, height: 900 } },
    { name: "desktop-1920", viewport: { width: 1920, height: 1080 } },
];

export default defineConfig({
    testDir: "./e2e/browser-contract",
    timeout: 45_000,
    fullyParallel: false,
    workers: 1,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI
        ? [
              ["line"],
              ["html", { open: "never", outputFolder: "playwright-report" }],
          ]
        : "line",
    use: {
        baseURL: "http://localhost:3100",
        screenshot: "only-on-failure",
        trace: "retain-on-failure",
        video: "off",
    },
    outputDir: "test-results",
    projects: viewports.map((project) => ({
        name: project.name,
        use: {
            browserName: "chromium",
            viewport: project.viewport,
        },
    })),
    webServer: [
        {
            command: "node e2e/browser-contract/mock-backend.mjs",
            url: "http://127.0.0.1:3101/__health",
            reuseExistingServer: !process.env.CI,
            timeout: 30_000,
        },
        {
            command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
            url: "http://127.0.0.1:3100",
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
            env: {
                DJANGO_API_URL: "http://127.0.0.1:3101",
                PUBLIC_SITE_URL: "http://localhost:3100",
                PREVIEW_COOKIE_SECURE: "false",
                PREVIEW_TOKEN_TTL_SECONDS: "600",
            },
        },
    ],
});
