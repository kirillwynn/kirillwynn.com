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
        expect(draftRoute).toContain("publicSiteUrl()");
        expect(draftRoute).not.toContain("request.url");
    });

    it("keeps Draft Mode redirects on the configured public origin", () => {
        const draftRoute = source("app/api/draft/route.ts");
        const disableRoute = source("app/api/draft/disable/route.ts");

        for (const route of [draftRoute, disableRoute]) {
            expect(route).toContain("publicSiteUrl()");
            expect(route).not.toContain("request.url");
        }
    });

    it("percent-encodes slugs in server-to-server content fetches", () => {
        const django = source("lib/server/django.ts");
        expect(django).toContain("encodeURIComponent(slug)");
    });

    it("keeps internal origins and secrets out of browser-facing modules", () => {
        for (const path of [
            "app/globals.css",
            "app/account/page.tsx",
            "app/login/page.tsx",
            "components/account-panel.tsx",
            "components/auth-provider.tsx",
            "components/comment-card.tsx",
            "components/comments-section.tsx",
            "components/feed-controls.tsx",
            "components/feed-stream.tsx",
            "components/login-panel.tsx",
            "components/provider-form.tsx",
            "components/site-header.tsx",
            "components/site-footer.tsx",
            "components/subscription-credential-action.tsx",
            "components/subscription-form.tsx",
            "components/thread-panel.tsx",
            "components/post-card.tsx",
            "components/post-body.tsx",
            "components/post-reactions.tsx",
            "components/preview-banner.tsx",
            "components/reaction-bar.tsx",
            "lib/bridge.ts",
            "lib/comment-drafts.ts",
            "lib/comments.ts",
            "lib/feed-state.ts",
            "lib/reaction-mutation-coordinator.ts",
            "lib/reaction-storage.ts",
            "lib/reactions.ts",
        ]) {
            const contents = source(path);
            expect(contents).not.toContain("DJANGO_API_URL");
            expect(contents).not.toContain("REVALIDATION_SECRET");
            expect(contents).not.toContain("http://localhost:8000");
            expect(contents).not.toContain("GOOGLE_OAUTH_CLIENT");
            expect(contents).not.toContain("GITHUB_OAUTH_CLIENT");
            expect(contents).not.toContain("RESEND_API_KEY");
            expect(contents).not.toContain("RESEND_WEBHOOK_SECRET");
            expect(contents).not.toContain("SUBSCRIPTION_SIGNING_SECRET");
            expect(contents).not.toContain("sessionid");
        }
    });

    it("uses only fixed same-origin auth rewrites and preserves Django slashes", () => {
        const config = source("next.config.ts");

        expect(config).toContain("skipTrailingSlashRedirect: true");
        expect(config).toContain('source: "/accounts/:path*/"');
        expect(config).toContain('source: "/api/me/"');
        expect(config).toContain('source: "/api/auth/logout/"');
        expect(config).toContain('source: "/api/v1/subscriptions/"');
        expect(config).toContain('source: "/api/v1/subscriptions/confirm/"');
        expect(config).toContain(
            'source: "/api/v1/subscriptions/unsubscribe/"',
        );
        expect(config).toContain(
            'source: "/api/v1/subscriptions/unsubscribe/one-click/"',
        );
        expect(config).toContain('source: "/api/v1/email/webhooks/resend/"');
        expect(config).toContain('source: "/api/v1/posts/:slug/comments/"');
        expect(config).toContain('source: "/api/v1/reactions/config/"');
        expect(config).toContain('source: "/api/v1/reactions/catalog/"');
        expect(config).toContain('source: "/api/v1/reactions/posts/"');
        expect(
            config.match(/source: "\/api\/v1\/reactions\/posts\/"/g),
        ).toHaveLength(1);
        expect(config).toContain(
            'source: "/api/v1/posts/:slug/reactions/toggle/"',
        );
        expect(config).toContain(
            'source: "/api/v1/posts/:slug/reactions/:reactionId/participants/"',
        );
        expect(config).toContain(
            'source: "/api/v1/comments/:id/reactions/toggle/"',
        );
        expect(config).toContain(
            'source: "/api/v1/comments/:id/reactions/:reactionId/participants/"',
        );
        expect(config).toContain('source: "/api/v1/comments/:id/thread/"');
        expect(config).toContain('source: "/api/v1/comments/:id/replies/"');
        expect(config).toContain('source: "/api/v1/comments/:id/"');
        expect(config).not.toContain("searchParams");
        expect(config).not.toContain("NEXT_PUBLIC_");
        expect(config).not.toContain('source: "/api/:path*"');
    });

    it("keeps one safe-area-aware shell contract without global overflow masking", () => {
        const css = source("app/globals.css");
        const mainRule = css.match(/\.site-main\s*\{[^}]*\}/)?.[0] ?? "";

        expect(css).toContain("env(safe-area-inset-left, 0px)");
        expect(css).toContain("env(safe-area-inset-right, 0px)");
        expect(mainRule).not.toContain("width: 100%");
        expect(css).not.toMatch(/(?:html|body)\s*\{[^}]*overflow-x:\s*hidden/s);
    });

    it("keeps Search and Bridge focus perceptible without contour or border recoloring", () => {
        const css = source("app/globals.css");
        const searchStart = css.indexOf(
            ".feed-search .feed-search-input:focus,",
        );
        const searchEnd = css.indexOf(".feed-search-input::placeholder");
        const searchStates = css.slice(searchStart, searchEnd);
        expect(searchStart).toBeGreaterThan(0);
        expect(searchStates).toContain(
            "border-color: var(--color-border-strong)",
        );
        expect(searchStates).toContain("outline: 0");
        expect(searchStates).toContain("box-shadow: none");
        expect(searchStates).toContain(
            "background: var(--color-surface-subtle)",
        );
        expect(searchStates).not.toContain("var(--color-accent);");

        const bridgeStart = css.indexOf(".bridge-link:hover,");
        const bridgeEnd = css.indexOf(".bridge-link img");
        const bridgeStates = css.slice(bridgeStart, bridgeEnd);
        expect(bridgeStart).toBeGreaterThan(0);
        expect(bridgeStates).toContain("outline: 0");
        expect(bridgeStates).toContain("box-shadow: none");
        expect(bridgeStates).toContain("border-color: var(--color-border)");
        expect(bridgeStates).toContain(
            "background: var(--color-surface-subtle)",
        );
        expect(bridgeStates).not.toContain("var(--color-accent)");
    });

    it("does not implement browser-stored auth tokens", () => {
        for (const path of [
            "components/account-panel.tsx",
            "components/auth-provider.tsx",
            "components/login-panel.tsx",
            "components/provider-form.tsx",
            "components/site-header.tsx",
            "lib/auth.ts",
        ]) {
            const contents = source(path);
            expect(contents).not.toContain("localStorage");
            expect(contents).not.toContain("sessionStorage");
            expect(contents).not.toContain("X-Session-Token");
            expect(contents).not.toContain("Authorization");
        }
    });

    it("keeps the custom catalog behind the lazy picker boundary without Unicode datasets", () => {
        const bar = source("components/reaction-bar.tsx");
        const picker = source("components/reaction-picker.tsx");
        const storage = source("lib/reaction-storage.ts");

        expect(bar).toContain(
            'lazy(() => import("@/components/reaction-picker"))',
        );
        expect(picker).toContain("getReactionCatalog");
        expect(picker).not.toContain("@emoji-mart/data");
        expect(storage).not.toContain('from "emoji-regex"');
        expect(storage).not.toContain("@emoji-mart/data");
        expect(bar).not.toContain("@emoji-mart/data");
    });
});
