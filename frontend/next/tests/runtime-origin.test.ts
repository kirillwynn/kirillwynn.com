import { readFileSync } from "node:fs";

import { afterEach, describe, expect, it, vi } from "vitest";

import { publicSiteUrl } from "@/lib/server/config";

afterEach(() => {
    vi.unstubAllEnvs();
});

describe("promotable runtime origin", () => {
    it("resolves two origins at runtime without a NEXT_PUBLIC build value", () => {
        vi.stubEnv("NODE_ENV", "production");
        vi.stubEnv("PUBLIC_SITE_URL", "https://staging.kirillwynn.com");
        expect(publicSiteUrl()).toBe("https://staging.kirillwynn.com");

        vi.stubEnv("PUBLIC_SITE_URL", "https://kirillwynn.com");
        expect(publicSiteUrl()).toBe("https://kirillwynn.com");
    });

    it("keeps metadata runtime-bound while allowing explicit public caches", () => {
        const layout = readFileSync(
            new URL("../app/layout.tsx", import.meta.url),
            "utf8",
        );
        expect(layout).not.toContain('dynamic = "force-dynamic"');
        expect(layout).toContain("await connection()");
        expect(layout).not.toContain("NEXT_PUBLIC_");
        expect(layout).toContain("THEME_INIT_SCRIPT");
        expect(layout).toContain("suppressHydrationWarning");
        expect(layout.indexOf("<head>")).toBeLessThan(layout.indexOf("<body"));
        const nextConfig = readFileSync(
            new URL("../next.config.ts", import.meta.url),
            "utf8",
        );
        expect(nextConfig).toContain("cacheComponents: true");
    });
});
