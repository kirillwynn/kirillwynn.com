import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Pagination } from "@/components/pagination";
import { PostCard } from "@/components/post-card";
import { PreviewBanner } from "@/components/preview-banner";
import { SiteHeader } from "@/components/site-header";
import type { ContentImage, PostListItem } from "@/lib/content-contract";
import { parsePageParam } from "@/lib/pagination";

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
    it("accepts only positive integer page query values", () => {
        expect(parsePageParam(undefined)).toBe(1);
        expect(parsePageParam("2")).toBe(2);
        expect(parsePageParam("0")).toBeNull();
        expect(parsePageParam("01")).toBeNull();
        expect(parsePageParam("1.5")).toBeNull();
        expect(parsePageParam(["1", "2"])).toBeNull();
    });

    it("percent-encodes Unicode post links once", () => {
        const html = renderToStaticMarkup(
            createElement(PostCard, { post: summary() }),
        );
        expect(html).toContain(
            'href="/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80"',
        );
        expect(html).not.toContain("%25D0");
    });

    it("renders accessible previous and next controls", () => {
        const html = renderToStaticMarkup(
            createElement(Pagination, {
                page: 2,
                hasPrevious: true,
                hasNext: true,
            }),
        );
        expect(html).toContain('aria-label="Feed pagination"');
        expect(html).toContain('href="/"');
        expect(html).toContain('href="/?page=3"');
        expect(html).toContain('rel="prev"');
        expect(html).toContain('rel="next"');
    });
});

describe("shell and preview controls", () => {
    it("reserves a stable account control while auth state loads", () => {
        const html = renderToStaticMarkup(createElement(SiteHeader));
        expect(html).toContain("Loading account");
        expect(html).toContain("min-w-20");
        expect(html).not.toContain('href="/accounts');
    });

    it("renders a prominent Draft Mode banner and working exit endpoint", () => {
        const html = renderToStaticMarkup(createElement(PreviewBanner));
        expect(html).toContain('aria-label="Draft preview"');
        expect(html).toContain("immutable snapshot");
        expect(html).toContain('href="/api/draft/disable"');
    });
});
