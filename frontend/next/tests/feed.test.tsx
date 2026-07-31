// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage, { generateMetadata } from "@/app/page";
import { FeedControls } from "@/components/feed-controls";
import type {
    AvailableTagResponse,
    PostListItem,
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

const { notFound, replace, draftState } = vi.hoisted(() => {
    return {
        replace: vi.fn(),
        draftState: { isEnabled: false },
        notFound: vi.fn(() => {
            throw new Error("NEXT_NOT_FOUND");
        }),
    };
});

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace }),
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
        tags: [{ name: "Notes", slug: "notes" }],
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

function renderControls(): {
    container: HTMLDivElement;
    root: Root;
    render: (state: { page: number; q?: string; tag?: string }) => void;
} {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    const render = (state: { page: number; q?: string; tag?: string }) => {
        act(() => {
            root.render(
                <FeedControls state={state} tags={availableTags.results} />,
            );
        });
    };
    render({ page: 4, q: "old query", tag: "питон" });
    return { container, root, render };
}

function setInputValue(input: HTMLInputElement | null, value: string): void {
    act(() => {
        const descriptor = Object.getOwnPropertyDescriptor(
            HTMLInputElement.prototype,
            "value",
        );
        if (descriptor?.set && input) {
            // The native prototype setter intentionally bypasses React's value tracker.
            // eslint-disable-next-line @typescript-eslint/unbound-method
            Reflect.apply(descriptor.set, input, [value]);
        }
        input?.dispatchEvent(new Event("input", { bubbles: true }));
    });
}

function submit(form: HTMLFormElement | null): void {
    act(() => {
        form?.dispatchEvent(
            new SubmitEvent("submit", {
                bubbles: true,
                cancelable: true,
            }),
        );
    });
}

function startComposition(input: HTMLInputElement | null): void {
    act(() => {
        input?.dispatchEvent(
            new CompositionEvent("compositionstart", {
                bubbles: true,
            }),
        );
    });
}

function endComposition(input: HTMLInputElement | null): void {
    act(() => {
        input?.dispatchEvent(
            new CompositionEvent("compositionend", {
                bubbles: true,
            }),
        );
    });
}

beforeEach(() => {
    draftState.isEnabled = false;
    replace.mockReset();
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
    vi.useRealTimers();
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
    it("debounces rapid Unicode input, preserves tag, resets page, and encodes once", () => {
        vi.useFakeTimers();
        const { container, root } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");
        expect(input?.value).toBe("old query");

        const values = ["н", "но", "нов", "  новый Django  "];
        for (const [index, value] of values.entries()) {
            setInputValue(input, value);
            if (index < values.length - 1) {
                act(() => {
                    vi.advanceTimersByTime(100);
                });
            }
        }
        expect(replace).not.toHaveBeenCalled();
        act(() => {
            vi.advanceTimersByTime(299);
        });
        expect(replace).not.toHaveBeenCalled();
        act(() => {
            vi.advanceTimersByTime(1);
        });

        expect(replace).toHaveBeenCalledOnce();
        expect(replace).toHaveBeenCalledWith(
            "/?q=%D0%BD%D0%BE%D0%B2%D1%8B%D0%B9+Django&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        expect(replace.mock.calls[0]?.[0]).not.toContain("%25D0");
        act(() => {
            root.unmount();
        });
    });

    it("submits immediately, cancels a stale timer, and avoids duplicate navigation", () => {
        vi.useFakeTimers();
        const { container, root, render } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");
        const form = container.querySelector<HTMLFormElement>("form");

        setInputValue(input, "stale");
        setInputValue(input, "  immediate query  ");
        submit(form);

        expect(replace).toHaveBeenCalledOnce();
        expect(replace).toHaveBeenCalledWith(
            "/?q=immediate+query&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        act(() => {
            vi.advanceTimersByTime(1_000);
        });
        expect(replace).toHaveBeenCalledOnce();

        replace.mockClear();
        render({ page: 1, q: "same", tag: "питон" });
        setInputValue(input, "same");
        act(() => {
            vi.advanceTimersByTime(300);
        });
        submit(form);
        expect(replace).not.toHaveBeenCalled();

        act(() => {
            root.unmount();
        });
    });

    it("removes q when the input is erased and keeps the active tag", () => {
        vi.useFakeTimers();
        const { container, root } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");

        setInputValue(input, "");
        act(() => {
            vi.advanceTimersByTime(300);
        });

        expect(replace).toHaveBeenCalledWith(
            "/?tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        expect(replace.mock.calls[0]?.[0]).not.toContain("q=");
        expect(replace.mock.calls[0]?.[0]).not.toContain("page=1");
        act(() => {
            root.unmount();
        });
    });

    it("lets the latest value supersede a navigation already in flight", () => {
        vi.useFakeTimers();
        const { container, root, render } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");

        setInputValue(input, "first navigation");
        act(() => {
            vi.advanceTimersByTime(300);
        });
        expect(replace).toHaveBeenLastCalledWith(
            "/?q=first+navigation&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );

        setInputValue(input, "old query");
        render({ page: 1, q: "first navigation", tag: "питон" });
        expect(input?.value).toBe("old query");
        act(() => {
            vi.advanceTimersByTime(300);
        });
        expect(replace).toHaveBeenLastCalledWith(
            "/?q=old+query&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        expect(replace).toHaveBeenCalledTimes(2);

        act(() => {
            root.unmount();
        });
    });

    it("suppresses intermediate IME navigation and starts debounce after composition", () => {
        vi.useFakeTimers();
        const { container, root } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");

        startComposition(input);
        setInputValue(input, "に");
        setInputValue(input, "日本");
        act(() => {
            vi.advanceTimersByTime(1_000);
        });
        expect(replace).not.toHaveBeenCalled();

        endComposition(input);
        act(() => {
            vi.advanceTimersByTime(299);
        });
        expect(replace).not.toHaveBeenCalled();
        act(() => {
            vi.advanceTimersByTime(1);
        });
        expect(replace).toHaveBeenCalledWith(
            "/?q=%E6%97%A5%E6%9C%AC&tag=%D0%BF%D0%B8%D1%82%D0%BE%D0%BD",
        );
        act(() => {
            root.unmount();
        });
    });

    it("syncs back/forward URL state and cancels the stale pending timer", () => {
        vi.useFakeTimers();
        const { container, root, render } = renderControls();
        const input = container.querySelector<HTMLInputElement>("#feed-search");

        setInputValue(input, "stale pending query");
        render({ page: 1, q: "back query", tag: "django" });
        expect(input?.value).toBe("back query");
        act(() => {
            vi.advanceTimersByTime(1_000);
        });
        expect(replace).not.toHaveBeenCalled();

        render({ page: 2, q: "forward query", tag: "django" });
        expect(input?.value).toBe("forward query");
        expect(replace).not.toHaveBeenCalled();
        act(() => {
            root.unmount();
        });
    });

    it("builds accessible tag links without separate clear controls", () => {
        const html = renderToStaticMarkup(
            <FeedControls
                state={{ page: 3, q: "django", tag: "питон" }}
                tags={availableTags.results}
            />,
        );

        expect(html).toContain('role="search"');
        expect(html).toContain('for="feed-search"');
        expect(html).toContain('value="django"');
        expect(html).not.toContain("Clear search");
        expect(html).not.toContain("Clear filters");
        expect(html).not.toContain("Clear tag");
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

        const html = renderToStaticMarkup(element);
        expect(html).toContain("Invalid Feed URL");
        expect(html).toContain('<h1 id="empty-feed-title">');
        expect(html).toContain('href="/"');
        expect(html).toContain("Return to Feed");
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
        const noResultsHtml = renderToStaticMarkup(noResults);
        expect(noResultsHtml).toContain("No posts found");
        expect(noResultsHtml).not.toContain("Clear filters");
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

    it("renders a compact stream before subscription and omits dead pagination", async () => {
        vi.mocked(getAvailableTags).mockResolvedValue(availableTags);
        vi.mocked(getPublicPosts).mockResolvedValue(
            feed({
                count: 1,
                results: [postSummary()],
            }),
        );

        const element = await HomePage({
            searchParams: Promise.resolve({}),
        });
        const html = renderToStaticMarkup(element);

        expect(html).toContain('<h1 class="sr-only">Feed</h1>');
        expect(html).toContain('aria-label="Latest posts"');
        expect(html).toContain("feed-entry");
        expect(html).not.toContain('aria-label="Feed pagination"');
        expect(html.indexOf("A quiet Feed entry")).toBeLessThan(
            html.indexOf("Get new posts by email"),
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
