import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

function source(path: string): string {
    return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

describe("server-only security boundary", () => {
    it("marks every runtime secret or preview transport module as server-only", () => {
        for (const path of [
            "lib/server/config.ts",
            "lib/server/django.ts",
            "lib/server/preview-cookies.ts",
            "lib/server/revalidation.ts",
        ]) {
            expect(source(path)).toContain('import "server-only"');
        }
    });

    it("never declares secrets as browser-exposed NEXT_PUBLIC values", () => {
        const config = source("lib/server/config.ts");
        expect(config).not.toContain("NEXT_PUBLIC_");
        expect(config).toContain("process.env.REVALIDATION_SECRET");
    });

    it("scopes the snapshot credential away from Django public API routes", () => {
        const draftRoute = source("app/api/draft/route.ts");
        expect(draftRoute).toContain('path: "/posts"');
        expect(draftRoute).not.toContain("searchParams");
    });
});
