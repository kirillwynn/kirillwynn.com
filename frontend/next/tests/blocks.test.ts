import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ContentBlockRenderer, PostBody } from "@/components/post-body";
import type { ContentBlock, ContentImage } from "@/lib/content-contract";

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

const blocks: ContentBlock[] = [
    {
        id: "rich",
        type: "rich_text",
        value: { html: "<p><strong>Expanded</strong> HTML</p>" },
    },
    {
        id: "heading",
        type: "heading",
        value: { level: "h2", text: "Heading" },
    },
    { id: "image", type: "image", value: image },
    {
        id: "gallery",
        type: "gallery",
        value: { images: [image] },
    },
    {
        id: "quote",
        type: "quote",
        value: { text: "Quote", attribution: "Author" },
    },
    {
        id: "bulleted",
        type: "bulleted_list",
        value: { items: ["Bullet"] },
    },
    {
        id: "numbered",
        type: "numbered_list",
        value: { items: ["Number"] },
    },
    {
        id: "checklist",
        type: "checklist",
        value: { items: [{ text: "Done", checked: true }] },
    },
    {
        id: "inline",
        type: "inline_code",
        value: { code: "const value = 1" },
    },
    {
        id: "code",
        type: "code_block",
        value: { language: "typescript", code: "const value = true;" },
    },
    {
        id: "table",
        type: "table",
        value: {
            rows: [
                ["Name", "Value"],
                ["One", "1"],
            ],
            header: { row: true, column: true },
        },
    },
    { id: "divider", type: "horizontal_divider", value: {} },
    {
        id: "link",
        type: "link",
        value: {
            text: "Internal",
            kind: "internal",
            href: "/posts/next",
            target: { id: 8, type: "blog.blogpostpage", slug: "next" },
        },
    },
];

describe("exhaustive StreamField renderer", () => {
    it("renders all 13 contract block variants", () => {
        expect(blocks).toHaveLength(13);
        const html = renderToStaticMarkup(createElement(PostBody, { blocks }));
        for (const expected of [
            "<strong>Expanded</strong>",
            "<h2",
            "<img",
            "Image gallery",
            "<blockquote",
            "<ul",
            "<ol",
            'type="checkbox"',
            "const value = 1",
            "code-keyword",
            "<table",
            "<hr",
            'href="/posts/next"',
        ]) {
            expect(html).toContain(expected);
        }
    });

    it("uses contextual or empty decorative alt and fixed responsive renditions", () => {
        const contextual = renderToStaticMarkup(
            createElement(ContentBlockRenderer, { block: blocks[2] }),
        );
        expect(contextual).toContain('alt="A snowy ridge"');
        expect(contextual).toContain('width="1440"');
        expect(contextual).toContain('height="960"');
        expect(contextual).toContain(
            "ridge-480.jpg 480w, https://cdn.example/ridge-960.jpg 960w, https://cdn.example/ridge-1440.jpg 1440w",
        );

        const decorative: ContentBlock = {
            id: "decorative",
            type: "image",
            value: { ...image, decorative: true, alt: "Ignored" },
        };
        const decorativeHtml = renderToStaticMarkup(
            createElement(ContentBlockRenderer, { block: decorative }),
        );
        expect(decorativeHtml).toContain('alt=""');
        expect(decorativeHtml).not.toContain("Ignored");
    });

    it("uses th scope for row and column headers", () => {
        const html = renderToStaticMarkup(
            createElement(ContentBlockRenderer, { block: blocks[9 + 1] }),
        );
        expect(html).toContain('scope="col"');
        expect(html).toContain('scope="row"');
        expect(html).toContain("<td");
    });

    it("opens safe external links securely and preserves internal paths", () => {
        const external: ContentBlock = {
            id: "external",
            type: "link",
            value: {
                text: "External",
                kind: "external",
                href: "https://example.com/path",
                target: null,
            },
        };
        const internal = renderToStaticMarkup(
            createElement(ContentBlockRenderer, { block: blocks[12] }),
        );
        const externalHtml = renderToStaticMarkup(
            createElement(ContentBlockRenderer, { block: external }),
        );
        expect(internal).toContain('href="/posts/next"');
        expect(internal).not.toContain('target="_blank"');
        expect(externalHtml).toContain('target="_blank"');
        expect(externalHtml).toContain('rel="noopener noreferrer"');
    });

    it.each([null, "javascript:alert(1)", "//evil.example"])(
        "does not create a broken or unsafe link for %s",
        (href) => {
            const unsafe: ContentBlock = {
                id: "unsafe",
                type: "link",
                value: {
                    text: "Unsafe",
                    kind: href?.startsWith("//") ? "internal" : "external",
                    href,
                    target: null,
                },
            };
            const html = renderToStaticMarkup(
                createElement(ContentBlockRenderer, { block: unsafe }),
            );
            expect(html).not.toContain("<a");
            expect(html).toContain("Unsafe");
        },
    );

    it("uses safe plain text for an unknown code language", () => {
        const unknown: ContentBlock = {
            id: "unknown",
            type: "code_block",
            value: {
                language: "future-lang",
                code: '<script>alert("no")</script>',
            },
        };
        const html = renderToStaticMarkup(
            createElement(ContentBlockRenderer, { block: unknown }),
        );
        expect(html).toContain("plain-text fallback");
        expect(html).toContain("&lt;script&gt;");
        expect(html).not.toContain("<script>");
    });
});
