import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PostCard } from "@/components/post-card";
import { PreviewBanner } from "@/components/preview-banner";
import { FooterContent } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import type { ContentImage, PostListItem } from "@/lib/content-contract";

export const image: ContentImage = {
    id: 7,
    title: "Ridge",
    alt: "A snowy ridge",
    decorative: false,
    width: 2400,
    height: 1600,
    renditions: {
        "480w": {
            url: "https://cdn.example/ridge-480.jpg",
            width: 480,
            height: 320,
        },
        "960w": {
            url: "https://cdn.example/ridge-960.jpg",
            width: 960,
            height: 640,
        },
        "1440w": {
            url: "https://cdn.example/ridge-1440.jpg",
            width: 1440,
            height: 960,
        },
    },
};

function summary(overrides: Partial<PostListItem> = {}): PostListItem {
    return {
        api_version: "1.0",
        id: 42,
        slug: "привет-мир",
        title: "Unicode post",
        excerpt: "A post excerpt.",
        published_at: "2026-07-26T17:00:00Z",
        updated_at: "2026-07-26T17:05:00Z",
        original_published_at: null,
        display_published_at: "2026-07-26T17:00:00Z",
        author: {
            id: 1,
            display_name: "Kirill Wynn",
            is_site_author: true,
        },
        tags: [{ name: "Django", slug: "django" }],
        canonical_path: "/posts/привет-мир",
        canonical_url: "https://example.com/posts/%D0%BF",
        seo: { title: "Unicode post", description: "A post excerpt." },
        open_graph: {
            title: "Unicode post",
            description: "A post excerpt.",
            image: null,
        },
        lead_image: image,
        ...overrides,
    };
}

describe("feed presentation", () => {
    it("percent-encodes Unicode post links once", () => {
        const html = renderToStaticMarkup(
            createElement(PostCard, { post: summary() }),
        );
        expect(html).toContain(
            'href="/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80"',
        );
        expect(html).not.toContain("%25D0");
        expect(html).toContain('class="feed-entry"');
        expect(html).not.toContain("#Django");
        expect(html).toContain("by Kirill Wynn");
    });

    it("renders the display publication date in the Feed time element", () => {
        const html = renderToStaticMarkup(
            createElement(PostCard, {
                post: summary({
                    published_at: "2026-07-26T17:00:00Z",
                    original_published_at: "2014-03-02T10:00:00Z",
                    display_published_at: "2014-03-02T10:00:00Z",
                }),
            }),
        );

        expect(html).toContain('<time dateTime="2014-03-02T10:00:00Z">');
        expect(html).not.toContain('<time dateTime="2026-07-26T17:00:00Z">');
    });
});

describe("shell and preview controls", () => {
    it("reserves a stable account control while auth state loads", () => {
        const html = renderToStaticMarkup(createElement(SiteHeader));
        expect(html).toContain("Loading account");
        expect(html).toContain("account-placeholder");
        expect(html).not.toContain("kirillwynn.com");
        expect(html).toContain('href="/">Feed</a>');
        expect(html).toContain('aria-label="Switch color theme"');
        expect(html).toContain('class="site-header__controls"');
        expect(html.indexOf('href="/">Feed</a>')).toBeLessThan(
            html.indexOf('href="/bridge">Bridge</a>'),
        );
        expect(html.indexOf('href="/bridge">Bridge</a>')).toBeLessThan(
            html.indexOf("theme-toggle"),
        );
        expect(html.indexOf("theme-toggle")).toBeLessThan(
            html.indexOf("account-slot"),
        );
        expect(html).not.toContain('href="/accounts');
    });

    it("renders a prominent Draft Mode banner and working exit endpoint", () => {
        const html = renderToStaticMarkup(createElement(PreviewBanner));
        expect(html).toContain('aria-label="Draft preview"');
        expect(html).toContain("immutable snapshot");
        expect(html).toContain('href="/api/draft/disable"');
    });

    it("renders the same two-line team-only footer for every route", () => {
        const html = renderToStaticMarkup(createElement(FooterContent));

        for (const value of [
            "Current Team",
            "Yandex",
            "Previous Team",
            "Deeplay",
        ]) {
            expect(html).toContain(value);
        }
        expect(html).not.toContain("©");
        expect(html).not.toContain("Kirill Wynn");
        expect(html).not.toContain(new Date().getUTCFullYear().toString());
        expect(html).not.toContain(
            "Writing about software, systems, and the work between.",
        );
        expect(html).toContain('aria-label="Team history"');
        expect(html).toContain("<dt>Current Team</dt><dd>Yandex</dd>");
        expect(html).toContain("<dt>Previous Team</dt><dd>Deeplay</dd>");
        expect(html).toContain('class="site-team-context"');
        expect(html.match(/<dt>/g)).toHaveLength(2);
        expect(html.match(/<dd>/g)).toHaveLength(2);
        expect(html).not.toContain("rounded");
        expect(html).not.toContain("shadow");
    });
});
