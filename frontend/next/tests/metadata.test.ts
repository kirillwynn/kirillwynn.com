import { describe, expect, it } from "vitest";

import type { ContentImage, PostDetail } from "@/lib/content-contract";
import { postMetadata } from "@/lib/metadata";

const image: ContentImage = {
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

function post(): PostDetail {
    return {
        api_version: "1.0",
        id: 42,
        slug: "metadata",
        title: "Fallback title",
        excerpt: "Fallback description",
        published_at: "2026-07-26T17:00:00Z",
        updated_at: "2026-07-26T18:00:00Z",
        tags: [{ name: "SEO", slug: "seo" }],
        canonical_path: "/posts/metadata",
        canonical_url: "https://kirillwynn.com/posts/metadata",
        seo: { title: "SEO title", description: "SEO description" },
        open_graph: {
            title: "Open Graph title",
            description: "Open Graph description",
            image,
        },
        body: [],
    };
}

describe("post metadata", () => {
    it("maps canonical, article timestamps, tags, and responsive image metadata", () => {
        const metadata = postMetadata(post(), false);
        expect(metadata.title).toBe("SEO title");
        expect(metadata.description).toBe("SEO description");
        expect(metadata.alternates?.canonical).toBe(
            "https://kirillwynn.com/posts/metadata",
        );
        expect(metadata.openGraph).toMatchObject({
            type: "article",
            title: "Open Graph title",
            description: "Open Graph description",
            publishedTime: "2026-07-26T17:00:00Z",
            modifiedTime: "2026-07-26T18:00:00Z",
            tags: ["SEO"],
            images: [
                {
                    url: "https://cdn.example/ridge-1440.jpg",
                    width: 1440,
                    height: 960,
                    alt: "A snowy ridge",
                },
            ],
        });
        expect(metadata.robots).toBeUndefined();
    });

    it("marks Draft Mode snapshots noindex, nofollow, and nocache", () => {
        expect(postMetadata(post(), true).robots).toMatchObject({
            index: false,
            follow: false,
            nocache: true,
        });
    });
});
