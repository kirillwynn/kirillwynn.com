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
        expect(config).toContain("process.env.PUBLIC_SITE_URL");
    });

    it("scopes the snapshot credential away from Django public API routes", () => {
        const draftRoute = source("app/api/draft/route.ts");
        expect(draftRoute).toContain('path: "/posts"');
        expect(draftRoute).not.toContain("searchParams");
        expect(draftRoute).toContain("previewCookieSecure()");
        expect(draftRoute).not.toContain("request.url).protocol");
    });

    it("percent-encodes slugs in server-to-server content fetches", () => {
        const django = source("lib/server/django.ts");
        expect(django).toContain("encodeURIComponent(slug)");
    });

    it("keeps internal origins and secrets out of browser-facing modules", () => {
        for (const path of [
            "app/globals.css",
            "components/site-header.tsx",
            "components/site-footer.tsx",
            "components/post-card.tsx",
            "components/post-body.tsx",
            "components/preview-banner.tsx",
            "lib/bridge.ts",
        ]) {
            const contents = source(path);
            expect(contents).not.toContain("DJANGO_API_URL");
            expect(contents).not.toContain("REVALIDATION_SECRET");
            expect(contents).not.toContain("http://localhost:8000");
        }
    });
});
