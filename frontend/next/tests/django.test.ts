import { afterEach, describe, expect, it, vi } from "vitest";

import {
    ContentApiError,
    getAvailableTags,
    getPublicPost,
    getPublicPosts,
    PreviewUnavailableError,
    resolvePreview,
} from "@/lib/server/django";

afterEach(() => {
    vi.unstubAllGlobals();
});

describe("Django content client", () => {
    it("fetches a validated list page with only the posts cache tag", async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    count: 0,
                    next: null,
                    previous: null,
                    results: [],
                }),
                { status: 200 },
            ),
        );
        vi.stubGlobal("fetch", fetchMock);

        await getPublicPosts({ page: 2 });

        expect(fetchMock).toHaveBeenCalledWith(
            "http://localhost:8000/api/v1/posts/?page=2",
            { next: { tags: ["posts"] } },
        );
    });

    it.each([0, -1, 1.5, Number.NaN, Number.MAX_SAFE_INTEGER + 1])(
        "rejects invalid page %s before fetching",
        async (page) => {
            const fetchMock = vi.fn();
            vi.stubGlobal("fetch", fetchMock);

            await expect(getPublicPosts({ page })).rejects.toThrow(
                "page must be a positive integer",
            );
            expect(fetchMock).not.toHaveBeenCalled();
        },
    );

    it("passes Unicode filters once and keeps the posts cache tag", async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    count: 0,
                    next: null,
                    previous: null,
                    results: [],
                }),
                { status: 200 },
            ),
        );
        vi.stubGlobal("fetch", fetchMock);

        await getPublicPosts({
            page: 2,
            q: "русский Django",
            tag: "питон",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            "http://localhost:8000/api/v1/posts/?q=%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9+Django&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD&page=2",
            { next: { tags: ["posts"] } },
        );
        expect(fetchMock.mock.calls[0]?.[0]).not.toContain("%25D1");
    });

    it("loads available tags with the shared posts cache tag", async () => {
        const fetchMock = vi
            .fn()
            .mockResolvedValue(
                new Response(JSON.stringify({ results: [] }), { status: 200 }),
            );
        vi.stubGlobal("fetch", fetchMock);

        await getAvailableTags();

        expect(fetchMock).toHaveBeenCalledWith(
            "http://localhost:8000/api/v1/tags/",
            { next: { tags: ["posts"] } },
        );
    });

    it("percent-encodes a Unicode slug and scopes the fetch cache", async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    id: 42,
                    slug: "привет-мир",
                }),
                { status: 200 },
            ),
        );
        vi.stubGlobal("fetch", fetchMock);

        await getPublicPost("привет-мир");

        expect(fetchMock).toHaveBeenCalledWith(
            "http://localhost:8000/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/",
            {
                next: {
                    tags: ["post-slug:привет-мир"],
                },
            },
        );
    });

    it("keeps API 404 distinct from an upstream failure", async () => {
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(new Response(null, { status: 404 }))
            .mockResolvedValueOnce(new Response(null, { status: 503 }));
        vi.stubGlobal("fetch", fetchMock);

        await expect(getPublicPost("missing")).resolves.toBeNull();
        await expect(getPublicPost("unavailable")).rejects.toBeInstanceOf(
            ContentApiError,
        );
    });

    it("keeps preview snapshots no-store and distinguishes expiry from infrastructure", async () => {
        const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(new Response(null, { status: 404 }))
            .mockResolvedValueOnce(new Response(null, { status: 500 }));
        vi.stubGlobal("fetch", fetchMock);

        await expect(resolvePreview("expired")).rejects.toBeInstanceOf(
            PreviewUnavailableError,
        );
        expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
            cache: "no-store",
        });
        await expect(
            resolvePreview("valid-but-upstream-failed"),
        ).rejects.toBeInstanceOf(ContentApiError);
    });
});
