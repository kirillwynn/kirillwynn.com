// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FeedPage, generateMetadata } from "@/app/page";
import { AuthProvider } from "@/components/auth-provider";
import { FeedControls } from "@/components/feed-controls";
import type { PostListItem, PostListResponse } from "@/lib/content-contract";
import {
    checkedNextFeedPath,
    feedApiPath,
    queryFromLocation,
} from "@/lib/feed-browser";
import {
    feedHref,
    MAX_QUERY_CODE_POINTS,
    parseFeedState,
} from "@/lib/feed-state";
import { ContentApiError, getPublicPosts } from "@/lib/server/django";

const { draftState, notFound, redirect } = vi.hoisted(() => ({
    draftState: { isEnabled: false },
    notFound: vi.fn(() => {
        throw new Error("NEXT_NOT_FOUND");
    }),
    redirect: vi.fn((href: string) => {
        throw new Error(`NEXT_REDIRECT:${href}`);
    }),
}));

vi.mock("next/navigation", () => ({
    notFound,
    redirect,
    usePathname: () => "/",
}));
vi.mock("next/headers", () => ({
    draftMode: () => Promise.resolve(draftState),
}));
vi.mock("@/lib/server/django", async (importOriginal) => {
    const original =
        await importOriginal<typeof import("@/lib/server/django")>();
    return { ...original, getPublicPosts: vi.fn() };
});

function feed(overrides: Partial<PostListResponse> = {}): PostListResponse {
    return {
        count: 0,
        next: null,
        previous: null,
        results: [],
        ...overrides,
    };
}

function postSummary(overrides: Partial<PostListItem> = {}): PostListItem {
    return {
        api_version: "1.0",
        id: 42,
        slug: "quiet-feed",
        title: "A quiet Feed entry",
        excerpt: "A compact message-like summary.",
        published_at: "2026-07-29T12:00:00Z",
        updated_at: "2026-07-29T12:00:00Z",
        original_published_at: null,
        display_published_at: "2026-07-29T12:00:00Z",
        author: {
            id: 1,
            display_name: "Kirill Wynn",
            is_site_author: true,
        },
        tags: [{ name: "Invisible tag", slug: "invisible-tag" }],
        canonical_path: "/posts/quiet-feed",
        canonical_url: "https://example.com/posts/quiet-feed",
        seo: {
            title: "A quiet Feed entry",
            description: "A compact message-like summary.",
        },
        open_graph: {
            title: "A quiet Feed entry",
            description: "A compact message-like summary.",
            image: null,
        },
        lead_image: null,
        ...overrides,
    };
}

function renderControls(
    query = "old query",
    onSearch = vi.fn<(query: string) => void>(),
): {
    container: HTMLDivElement;
    onSearch: typeof onSearch;
    render: (query: string) => void;
    root: Root;
} {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    const render = (nextQuery: string) => {
        act(() => {
            root.render(
                <FeedControls
                    onSearch={onSearch}
                    query={nextQuery}
                    searching={false}
                />,
            );
        });
    };
    render(query);
    return { container, onSearch, render, root };
}

function setInputValue(input: HTMLInputElement | null, value: string): void {
    act(() => {
        const descriptor = Object.getOwnPropertyDescriptor(
            HTMLInputElement.prototype,
            "value",
        );
        if (descriptor?.set && input) {
            // eslint-disable-next-line @typescript-eslint/unbound-method
            Reflect.apply(descriptor.set, input, [value]);
        }
        input?.dispatchEvent(new Event("input", { bubbles: true }));
    });
}

function submit(form: HTMLFormElement | null): void {
    act(() => {
        form?.dispatchEvent(
            new SubmitEvent("submit", { bubbles: true, cancelable: true }),
        );
    });
}

function renderHome(element: React.ReactNode): string {
    return renderToStaticMarkup(<AuthProvider>{element}</AuthProvider>);
}

beforeEach(() => {
    draftState.isEnabled = false;
    notFound.mockClear();
    redirect.mockClear();
    vi.mocked(getPublicPosts).mockReset();
    window.history.replaceState({}, "", "/");
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
});

describe("Feed URL and transport state", () => {
    it("keeps backend tag/page parsing compatible while encoding Unicode once", () => {
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
        expect(parseFeedState({ q: "safe\u0000hidden" })).toEqual({
            valid: false,
        });
        expect(
            parseFeedState({ q: "🔥".repeat(MAX_QUERY_CODE_POINTS + 1) }),
        ).toEqual({ valid: false });
        expect(parseFeedState({ page_size: "5" })).toEqual({ valid: false });

        const href = feedHref({ q: "русский Django", page: 1 });
        expect(href).toBe(
            "/?q=%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9+Django",
        );
        expect(href).not.toContain("page=1");
        expect(href).not.toContain("%25D1");
    });

    it("accepts only a verified same-origin post-list continuation", () => {
        expect(feedApiPath("日本語")).toBe(
            "/api/v1/posts/?q=%E6%97%A5%E6%9C%AC%E8%AA%9E",
        );
        expect(
            checkedNextFeedPath(
                "https://example.com/api/v1/posts/?q=%E6%97%A5%E6%9C%AC%E8%AA%9E&page=2",
                "日本語",
                "https://example.com",
            ),
        ).toBe("/api/v1/posts/?q=%E6%97%A5%E6%9C%AC%E8%AA%9E&page=2");
        for (const unsafe of [
            "https://evil.example/api/v1/posts/?page=2",
            "//evil.example/api/v1/posts/?page=2",
            "/api/v1/comments/?page=2",
            "/api/v1/posts/?page=2&tag=hidden",
            "/api/v1/posts/?page=2&q=other",
        ]) {
            expect(() =>
                checkedNextFeedPath(unsafe, "", "https://example.com"),
            ).toThrow();
        }
    });

    it("reads a single Unicode q value from browser history", () => {
        window.history.replaceState({}, "", "/?q=%E6%97%A5%E6%9C%AC");
        expect(queryFromLocation(window.location)).toBe("日本");
        window.history.replaceState({}, "", "/?q=one&q=two");
        expect(queryFromLocation(window.location)).toBe("");
    });
});

describe("client-cached Feed search controls", () => {
    it("debounces Unicode input for 275ms and submits immediately", () => {
        vi.useFakeTimers();
        const { container, onSearch, root } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");
        const form = container.querySelector<HTMLFormElement>("form");
        expect(input?.value).toBe("old query");

        setInputValue(input, "  новый Django  ");
        act(() => {
            vi.advanceTimersByTime(274);
        });
        expect(onSearch).not.toHaveBeenCalled();
        act(() => {
            vi.advanceTimersByTime(1);
        });
        expect(onSearch).toHaveBeenCalledWith("новый Django");

        onSearch.mockClear();
        setInputValue(input, " immediate ");
        submit(form);
        expect(onSearch).toHaveBeenCalledOnce();
        expect(onSearch).toHaveBeenCalledWith("immediate");
        act(() => {
            vi.advanceTimersByTime(1_000);
        });
        expect(onSearch).toHaveBeenCalledOnce();
        act(() => {
            root.unmount();
        });
    });

    it("is IME-safe, clears through ordinary typing, and follows history props", () => {
        vi.useFakeTimers();
        const { container, onSearch, render, root } = renderControls("日本");
        const input = container.querySelector<HTMLInputElement>("#feed-search");
        act(() => {
            input?.dispatchEvent(
                new CompositionEvent("compositionstart", { bubbles: true }),
            );
        });
        setInputValue(input, "日本語");
        act(() => {
            vi.advanceTimersByTime(1_000);
        });
        expect(onSearch).not.toHaveBeenCalled();
        act(() => {
            input?.dispatchEvent(
                new CompositionEvent("compositionend", { bubbles: true }),
            );
            vi.advanceTimersByTime(275);
        });
        expect(onSearch).toHaveBeenCalledWith("日本語");

        setInputValue(input, "");
        act(() => {
            vi.advanceTimersByTime(275);
        });
        expect(onSearch).toHaveBeenLastCalledWith("");
        render("back query");
        expect(input?.value).toBe("back query");
        act(() => {
            root.unmount();
        });
    });

    it("renders only search and the dedicated Subscribe link", () => {
        const html = renderToStaticMarkup(
            <FeedControls
                onSearch={() => undefined}
                query={'"><script>alert(1)</script>'}
                searching={false}
            />,
        );
        expect(html).toContain('role="search"');
        expect(html).toContain('href="/subscriptions"');
        expect(html).toContain(
            'value="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"',
        );
        expect(html).not.toContain("<script>");
        expect(html).not.toContain("#Django");
        expect(html).not.toContain("Clear search");
        expect(html).not.toContain("Page ");
    });
});

describe("Feed SSR response states and metadata", () => {
    it("renders invalid q without contacting Django", async () => {
        const element = await FeedPage({
            searchParams: Promise.resolve({ q: ["one", "two"] }),
        });
        expect(renderHome(element)).toContain("Invalid Feed URL");
        expect(getPublicPosts).not.toHaveBeenCalled();
    });

    it("normalizes legacy tag/page URLs to q without a loop", async () => {
        await expect(
            FeedPage({
                searchParams: Promise.resolve({
                    q: "русский Django",
                    tag: "питон",
                    page: "3",
                }),
            }),
        ).rejects.toThrow(
            "NEXT_REDIRECT:/?q=%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9+Django",
        );
        expect(getPublicPosts).not.toHaveBeenCalled();
        expect(redirect).toHaveBeenCalledOnce();
    });

    it("SSR-renders page one without tags, pagination, or subscription form", async () => {
        vi.mocked(getPublicPosts).mockResolvedValue(
            feed({ count: 1, results: [postSummary()] }),
        );
        const element = await FeedPage({ searchParams: Promise.resolve({}) });
        const html = renderHome(element);
        expect(html).toContain('<h1 class="sr-only">Feed</h1>');
        expect(html).toContain('aria-label="Latest posts"');
        expect(html).toContain("A quiet Feed entry");
        expect(html).toContain("Beginning of the archive");
        expect(html).not.toContain("Invisible tag");
        expect(html).not.toContain("Feed pagination");
        expect(html).not.toContain("Get new posts by email");
    });

    it("keeps search no-results, ordinary empty, 404, and infrastructure errors distinct", async () => {
        vi.mocked(getPublicPosts).mockResolvedValue(feed());
        const noResults = await FeedPage({
            searchParams: Promise.resolve({ q: "missing" }),
        });
        expect(renderHome(noResults)).toContain("No posts found");

        const empty = await FeedPage({ searchParams: Promise.resolve({}) });
        expect(renderHome(empty)).toContain("No published posts yet");

        vi.mocked(getPublicPosts).mockResolvedValueOnce(null);
        await expect(
            FeedPage({ searchParams: Promise.resolve({}) }),
        ).rejects.toThrow("NEXT_NOT_FOUND");

        vi.mocked(getPublicPosts).mockRejectedValueOnce(
            new ContentApiError("upstream unavailable"),
        );
        await expect(
            FeedPage({ searchParams: Promise.resolve({ q: "django" }) }),
        ).rejects.toBeInstanceOf(ContentApiError);
    });

    it("noindexes direct search while retaining the root canonical", async () => {
        const metadata = await generateMetadata({
            searchParams: Promise.resolve({ q: "<script>" }),
        });
        expect(metadata.alternates).toEqual({ canonical: "/" });
        expect(metadata.robots).toEqual({ index: false, follow: true });
        expect(JSON.stringify(metadata)).not.toContain("<script>");
    });
});
