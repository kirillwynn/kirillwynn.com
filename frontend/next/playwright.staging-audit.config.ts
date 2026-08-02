import { defineConfig } from "@playwright/test";

const credential = process.env.STAGING_BASIC_AUTH ?? "";
const separator = credential.indexOf(":");
if (separator < 1 || separator === credential.length - 1) {
    throw new Error(
        "STAGING_BASIC_AUTH must use a non-empty user:password value",
    );
}

const viewports = [
    { name: "mobile-320", viewport: { width: 320, height: 812 } },
    { name: "mobile-375", viewport: { width: 375, height: 812 } },
    { name: "tablet-768", viewport: { width: 768, height: 1024 } },
    { name: "desktop-1440", viewport: { width: 1440, height: 900 } },
    { name: "desktop-1920", viewport: { width: 1920, height: 1080 } },
];

export default defineConfig({
    testDir: "./e2e/staging-audit",
    timeout: 90_000,
    fullyParallel: false,
    workers: 1,
    retries: 1,
    reporter: "line",
    use: {
        baseURL: "https://staging.kirillwynn.com",
        browserName: "chromium",
        colorScheme: "dark",
        httpCredentials: {
            username: credential.slice(0, separator),
            password: credential.slice(separator + 1),
        },
        screenshot: "off",
        trace: "off",
        video: "off",
    },
    outputDir:
        process.env.STAGING_AUDIT_OUTPUT_DIR ??
        "/tmp/kirillwynn-stage18-playwright",
    projects: viewports.map((project) => ({
        name: project.name,
        use: { viewport: project.viewport },
    })),
});
