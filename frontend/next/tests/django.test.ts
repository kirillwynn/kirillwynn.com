import { afterEach, describe, expect, it, vi } from "vitest";

import { getPublicPost } from "@/lib/server/django";

afterEach(() => {
    vi.unstubAllGlobals();
});

describe("Django content client", () => {
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
});
