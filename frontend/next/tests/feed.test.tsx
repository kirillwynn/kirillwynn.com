// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage, { generateMetadata } from "@/app/page";
import { FeedControls } from "@/components/feed-controls";
import type {
    AvailableTagResponse,
    PostListResponse,
} from "@/lib/content-contract";
import {
    feedHref,
    MAX_QUERY_CODE_POINTS,
    parseFeedState,
} from "@/lib/feed-state";
import {
    ContentApiError,
    getAvailableTags,
    getPublicPosts,
} from "@/lib/server/django";

const { notFound, push, draftState } = vi.hoisted(() => {
    return {
        push: vi.fn(),
        draftState: { isEnabled: false },
        notFound: vi.fn(() => {
            throw new Error("NEXT_NOT_FOUND");
        }),
    };
});

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push }),
    notFound,
}));

vi.mock("next/headers", () => ({
    draftMode: () => Promise.resolve(draftState),
}));

vi.mock("@/lib/server/django", async (importOriginal) => {
    const original =
        await importOriginal<typeof import("@/lib/server/django")>();
    return {
        ...original,
        getPublicPosts: vi.fn(),
        getAvailableTags: vi.fn(),
    };
});

const availableTags: AvailableTagResponse = {
    results: [
        { name: "Django", slug: "django", count: 3 },
        { name: "Питон", slug: "питон", count: 2 },
    ],
};

function feed(overrides: Partial<PostListResponse> = {}): PostListResponse {
    return {
        count: 0,
        next: null,
        previous: null,
        results: [],
        ...overrides,
    };
}

function renderControls(): {
    container: HTMLDivElement;
    root: Root;
} {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(
            <FeedControls
                state={{ page: 4, q: "old query", tag: "питон" }}
                tags={availableTags.results}
            />,
        );
    });
    return { container, root };
}

beforeEach(() => {
    draftState.isEnabled = false;
    push.mockReset();
    notFound.mockClear();
    vi.mocked(getPublicPosts).mockReset();
    vi.mocked(getAvailableTags).mockReset();
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    document.body.replaceChildren();
});

describe("Feed URL state", () => {
    it("parses, trims, and rejects ambiguous or invalid parameter shapes", () => {
        expect(
            parseFeedState({
                q: "  русский Django  ",
                tag: "питон",
                page: "2",
            }),
        ).toEqual({
            valid: true,
            state: { q: "русский Django", tag: "питон", page: 2 },
        });
        expect(parseFeedState({ q: ["one", "two"] })).toEqual({
            valid: false,
        });
        expect(parseFeedState({ tag: "not a slug" })).toEqual({
            valid: false,
        });
        expect(parseFeedState({ q: "safe\u0000hidden" })).toEqual({
            valid: false,
        });
        expect(
            parseFeedState({ q: "🔥".repeat(MAX_QUERY_CODE_POINTS + 1) }),
        ).toEqual({ valid: false });
        expect(parseFeedState({ page: "01" })).toEqual({ valid: false });
        expect(parseFeedState({ page_size: "5" })).toEqual({ valid: false });
    });

    it("serializes Unicode once and omits page one", () => {
        const href = feedHref({
            q: "русский Django",
            tag: "питон",
            page: 1,
        });

        expect(href).toBe(
            "/?q=%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9+Django&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        expect(href).not.toContain("page=1");
        expect(href).not.toContain("%25D1");
    });
});

describe("Feed search and tag controls", () => {
    it("submits a trimmed search, preserves tag, and resets page", () => {
        const { container, root } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");
        const form = container.querySelector("form");
        expect(input?.value).toBe("old query");
        expect(form).not.toBeNull();

        act(() => {
            const descriptor = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                "value",
            );
            if (descriptor?.set && input) {
                // The native prototype setter intentionally bypasses React's value tracker.
                // eslint-disable-next-line @typescript-eslint/unbound-method
                Reflect.apply(descriptor.set, input, ["  новый Django  "]);
            }
            input?.dispatchEvent(new Event("input", { bubbles: true }));
        });
        act(() => {
            form?.dispatchEvent(
                new SubmitEvent("submit", {
                    bubbles: true,
                    cancelable: true,
                }),
            );
        });

        expect(push).toHaveBeenCalledWith(
            "/?q=%D0%BD%D0%BE%D0%B2%D1%8B%D0%B9+Django&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        act(() => {
            root.unmount();
        });
    });

    it("builds accessible search-clear, tag-select, and tag-clear links", () => {
        const html = renderToStaticMarkup(
            <FeedControls
                state={{ page: 3, q: "django", tag: "питон" }}
                tags={availableTags.results}
            />,
        );

        expect(html).toContain('role="search"');
        expect(html).toContain('for="feed-search"');
        expect(html).toContain('value="django"');
        expect(html).toContain("Clear search");
        expect(html).toContain("Clear tag");
        expect(html).toContain('aria-current="page"');
        expect(html).toContain('href="/?q=django&amp;tag=django"');
        expect(html).toContain('href="/?q=django"');
        expect(html).not.toContain("page=3");
    });

    it("escapes the current query instead of rendering HTML", () => {
        const html = renderToStaticMarkup(
            <FeedControls
                state={{ page: 1, q: '"><script>alert(1)</script>' }}
                tags={[]}
            />,
        );

        expect(html).not.toContain("<script>");
        expect(html).toContain(
            'value="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"',
        );
    });
});

describe("Feed response states and metadata", () => {
    it("renders invalid parameters without calling the backend", async () => {
        const element = await HomePage({
            searchParams: Promise.resolve({ q: ["one", "two"] }),
        });

        expect(renderToStaticMarkup(element)).toContain("Invalid Feed URL");
        expect(getPublicPosts).not.toHaveBeenCalled();
        expect(getAvailableTags).not.toHaveBeenCalled();
    });

    it("renders distinct unknown-tag and filtered no-results states", async () => {
        vi.mocked(getAvailableTags).mockResolvedValue(availableTags);
        vi.mocked(getPublicPosts).mockResolvedValue(feed());

        const unknown = await HomePage({
            searchParams: Promise.resolve({ tag: "unknown" }),
        });
        const noResults = await HomePage({
            searchParams: Promise.resolve({ q: "missing", tag: "django" }),
        });

        expect(renderToStaticMarkup(unknown)).toContain("Unknown tag");
        expect(renderToStaticMarkup(noResults)).toContain("No posts found");
    });

    it("omits the subscription form while Draft Mode is active", async () => {
        draftState.isEnabled = true;
        vi.mocked(getAvailableTags).mockResolvedValue(availableTags);
        vi.mocked(getPublicPosts).mockResolvedValue(feed());

        const element = await HomePage({
            searchParams: Promise.resolve({}),
        });

        expect(renderToStaticMarkup(element)).not.toContain(
            "Get new posts by email",
        );
    });

    it("keeps a backend 404 distinct from infrastructure failure", async () => {
        vi.mocked(getAvailableTags).mockResolvedValue(availableTags);
        vi.mocked(getPublicPosts).mockResolvedValueOnce(null);

        await expect(
            HomePage({
                searchParams: Promise.resolve({ page: "999" }),
            }),
        ).rejects.toThrow("NEXT_NOT_FOUND");
        expect(notFound).toHaveBeenCalledOnce();

        vi.mocked(getPublicPosts).mockRejectedValueOnce(
            new ContentApiError("upstream unavailable"),
        );
        await expect(
            HomePage({ searchParams: Promise.resolve({ q: "django" }) }),
        ).rejects.toBeInstanceOf(ContentApiError);
    });

    it("noindexes search/filter variants while keeping the root canonical", async () => {
        const metadata = await generateMetadata({
            searchParams: Promise.resolve({
                q: "<script>",
                tag: "django",
            }),
        });

        expect(metadata.alternates).toEqual({ canonical: "/" });
        expect(metadata.robots).toEqual({ index: false, follow: true });
        expect(JSON.stringify(metadata)).not.toContain("<script>");
    });
});
