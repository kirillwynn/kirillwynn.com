import { afterEach, describe, expect, it, vi } from "vitest";

import {
    previewCookieSecure,
    publicSiteUrl,
    revalidationSecret,
} from "@/lib/server/config";

afterEach(() => {
    vi.unstubAllEnvs();
});

describe("runtime production hardening", () => {
    it("requires at least 32 UTF-8 bytes for revalidation", () => {
        vi.stubEnv("REVALIDATION_SECRET", "short");
        expect(() => revalidationSecret()).toThrow(
            "REVALIDATION_SECRET must be at least 32 bytes",
        );

        vi.stubEnv("REVALIDATION_SECRET", "é".repeat(16));
        expect(revalidationSecret()).toBe("é".repeat(16));
    });

    it("always secures preview cookies in production", () => {
        vi.stubEnv("NODE_ENV", "production");
        expect(previewCookieSecure()).toBe(true);
    });

    it("keeps local HTTP preview cookies usable", () => {
        vi.stubEnv("NODE_ENV", "development");
        expect(previewCookieSecure()).toBe(false);
    });

    it("defaults the public origin locally and validates configured origins", () => {
        vi.stubEnv("NODE_ENV", "development");
        vi.stubEnv("PUBLIC_SITE_URL", "");
        expect(publicSiteUrl()).toBe("http://localhost:3000");

        vi.stubEnv("PUBLIC_SITE_URL", "https://kirillwynn.com/");
        expect(publicSiteUrl()).toBe("https://kirillwynn.com");

        vi.stubEnv("PUBLIC_SITE_URL", "https://example.com/path");
        expect(() => publicSiteUrl()).toThrow(
            "PUBLIC_SITE_URL must be an HTTP(S) origin",
        );
    });

    it("requires the public origin in production", () => {
        vi.stubEnv("NODE_ENV", "production");
        vi.stubEnv("PUBLIC_SITE_URL", "");
        expect(() => publicSiteUrl()).toThrow(
            "PUBLIC_SITE_URL is required in production",
        );
    });
});
