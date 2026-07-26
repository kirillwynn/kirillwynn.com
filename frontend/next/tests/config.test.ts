import { afterEach, describe, expect, it, vi } from "vitest";

import { previewCookieSecure, revalidationSecret } from "@/lib/server/config";

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
});
