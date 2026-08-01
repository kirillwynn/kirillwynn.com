import { describe, expect, it, vi } from "vitest";

import { enterDraftMode, verifiedPreviewPath } from "@/lib/draft-entry";
import type { PostDetail } from "@/lib/content-contract";

function post(overrides: Partial<PostDetail> = {}): PostDetail {
    return {
        api_version: "1.0",
        id: 42,
        slug: "bound-snapshot",
        title: "Preview",
        excerpt: "Preview excerpt",
        published_at: null,
        updated_at: null,
        original_published_at: null,
        display_published_at: null,
        author: {
            id: 1,
            display_name: "Kirill Wynn",
            is_site_author: true,
        },
        tags: [],
        canonical_path: "/posts/bound-snapshot",
        canonical_url: "https://example.com/posts/bound-snapshot",
        seo: { title: "Preview", description: "Preview excerpt" },
        open_graph: {
            title: "Preview",
            description: "Preview excerpt",
            image: null,
        },
        body: [],
        ...overrides,
    };
}

describe("Draft Mode entry", () => {
    it("verifies one credential, enables Draft Mode, and derives the redirect", async () => {
        const resolve = vi.fn().mockResolvedValue(post());
        const enable = vi.fn().mockResolvedValue(undefined);

        const result = await enterDraftMode(
            "opaque-credential",
            resolve,
            enable,
        );

        expect(result).toEqual({
            ok: true,
            path: "/posts/bound-snapshot",
            credential: "opaque-credential",
        });
        if (result.ok) {
            expect(result.path).not.toContain(result.credential);
            expect(new URL(result.path, "https://example.com").search).toBe("");
        }
        expect(resolve).toHaveBeenCalledWith("opaque-credential");
        expect(enable).toHaveBeenCalledOnce();
    });

    it("rejects missing, invalid, and expired credentials without enabling", async () => {
        const enable = vi.fn().mockResolvedValue(undefined);
        const reject = vi.fn().mockRejectedValue(new Error("unavailable"));

        await expect(
            enterDraftMode(undefined, reject, enable),
        ).resolves.toEqual({
            ok: false,
        });
        await expect(
            enterDraftMode("expired", reject, enable),
        ).resolves.toEqual({
            ok: false,
        });
        expect(enable).not.toHaveBeenCalled();
    });

    it("does not accept a redirect target from outside the verified response", () => {
        expect(
            verifiedPreviewPath(
                post({
                    canonical_path: "https://attacker.example/",
                }),
            ),
        ).toBeNull();
        expect(
            verifiedPreviewPath(
                post({ canonical_path: "/posts/another-post" }),
            ),
        ).toBeNull();
    });

    it("derives the real Next route for a Unicode slug", async () => {
        const resolve = vi.fn().mockResolvedValue(
            post({
                slug: "привет-мир",
                canonical_path: "/posts/привет-мир",
                canonical_url:
                    "https://example.com/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80",
            }),
        );

        await expect(
            enterDraftMode("opaque-credential", resolve, vi.fn()),
        ).resolves.toMatchObject({
            ok: true,
            path: "/posts/привет-мир",
        });
    });
});
