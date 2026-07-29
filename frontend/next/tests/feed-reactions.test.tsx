// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/auth-provider";
import { FeedStream } from "@/components/feed-stream";
import type { MeResponse } from "@/lib/auth";
import type { PostListItem } from "@/lib/content-contract";
import { resetReactionMutationCoordinatorForTests } from "@/lib/reaction-mutation-coordinator";

const signedIn: MeResponse = {
    authenticated: true,
    user: {
        id: 42,
        display_name: "Reader",
        email: "reader@example.com",
        is_admin: false,
        is_banned: false,
        can_interact: true,
    },
    providers: {
        google: { available: true, connected: true },
        github: { available: true, connected: false },
    },
    csrf_token: "masked-csrf",
};

function post(id: number): PostListItem {
    const slug = id === 1 ? "привет-мир" : `feed-post-${String(id)}`;
    return {
        api_version: "1.0",
        id,
        slug,
        title: `Feed post ${String(id)}`,
        excerpt: `Excerpt ${String(id)}.`,
        published_at: "2026-07-29T12:00:00Z",
        updated_at: "2026-07-29T12:00:00Z",
        tags: [],
        canonical_path: `/posts/${slug}`,
        canonical_url: `https://example.com/posts/${slug}`,
        seo: {
            title: `Feed post ${String(id)}`,
            description: `Excerpt ${String(id)}.`,
        },
        open_graph: {
            title: `Feed post ${String(id)}`,
            description: `Excerpt ${String(id)}.`,
            image: null,
        },
        lead_image: null,
    };
}

function response(payload: unknown, status = 200): Response {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}

function urlOf(input: RequestInfo | URL): string {
    return typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
}

function buttonByLabel(
    container: ParentNode,
    label: string,
): HTMLButtonElement | undefined {
    return Array.from(
        container.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.getAttribute("aria-label") === label);
}

async function waitFor(
    predicate: () => boolean,
    attempts = 100,
): Promise<void> {
    for (let index = 0; index < attempts; index += 1) {
        await act(async () => {
            await new Promise((resolve) => {
                setTimeout(resolve, 5);
            });
        });
        if (predicate()) {
            return;
        }
    }
    throw new Error("Timed out waiting for Feed reaction state.");
}

function renderFeed(
    posts: PostListItem[],
    loadReactions = true,
): {
    container: HTMLDivElement;
    root: Root;
} {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(
            <AuthProvider>
                <FeedStream loadReactions={loadReactions} posts={posts} />
            </AuthProvider>,
        );
    });
    return { container, root };
}

beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    resetReactionMutationCoordinatorForTests();
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
});

describe("Feed reaction hydration", () => {
    it("uses one private batch request and renders only compact existing pills", async () => {
        const posts = Array.from({ length: 10 }, (_, index) => post(index + 1));
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                return Promise.resolve(response(signedIn));
            }
            if (url === "/api/v1/reactions/posts/?ids=1,2,3,4,5,6,7,8,9,10") {
                return Promise.resolve(
                    response({
                        results: [
                            {
                                post_id: 1,
                                slug: "привет-мир",
                                reactions: [
                                    {
                                        emoji: "👍",
                                        count: 1,
                                        viewer_reacted: true,
                                        participants:
                                            "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/%F0%9F%91%8D/participants/",
                                    },
                                ],
                            },
                        ],
                    }),
                );
            }
            if (url.endsWith("/participants/")) {
                return Promise.resolve(
                    response({
                        next: null,
                        previous: null,
                        results: [
                            {
                                id: 42,
                                display_name: "Reader",
                                is_site_author: false,
                            },
                        ],
                    }),
                );
            }
            return Promise.reject(new Error(`Unexpected request: ${url}`));
        });

        const { container, root } = renderFeed(posts);
        await waitFor(() => vi.mocked(fetch).mock.calls.length >= 2);
        expect(
            vi.mocked(fetch).mock.calls.map(([input]) => urlOf(input)),
        ).toEqual(
            expect.arrayContaining([
                "/api/me/",
                "/api/v1/reactions/posts/?ids=1,2,3,4,5,6,7,8,9,10",
            ]),
        );
        await waitFor(
            () => buttonByLabel(container, "Remove 👍 reaction") !== undefined,
        );

        const calls = vi.mocked(fetch).mock.calls;
        const batchCalls = calls.filter(([input]) =>
            urlOf(input).startsWith("/api/v1/reactions/posts/?ids="),
        );
        expect(batchCalls).toHaveLength(1);
        expect(batchCalls[0]?.[1]).toMatchObject({
            cache: "no-store",
            credentials: "same-origin",
        });
        expect(
            calls.filter(([input]) =>
                /^\/api\/v1\/posts\/.+\/reactions\/$/.test(urlOf(input)),
            ),
        ).toHaveLength(0);
        expect(
            calls.some(
                ([input]) => urlOf(input) === "/api/v1/reactions/config/",
            ),
        ).toBe(false);
        expect(
            container.querySelector(
                'button[aria-label="Open full emoji picker"]',
            ),
        ).toBeNull();
        expect(container.querySelector(".quick-reaction")).toBeNull();
        const toggle = buttonByLabel(container, "Remove 👍 reaction");
        expect(toggle?.getAttribute("aria-pressed")).toBe("true");

        const participants = buttonByLabel(
            container,
            "View 1 participant for 👍",
        );
        act(() => {
            participants?.click();
        });
        await waitFor(() => {
            const dialog = container.querySelector('[role="dialog"]');
            return (
                dialog?.getAttribute("aria-label") ===
                "👍 reaction participants"
            );
        });
        expect(container.textContent).toContain("Reader");

        act(() => {
            root.unmount();
        });
    });

    it("leaves cards intact and emits no repeated errors when the batch fails", async () => {
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                return Promise.resolve(response(signedIn));
            }
            if (url === "/api/v1/reactions/posts/?ids=1,2") {
                return Promise.resolve(
                    response({ detail: "Unavailable" }, 503),
                );
            }
            return Promise.reject(new Error(`Unexpected request: ${url}`));
        });

        const { container, root } = renderFeed([post(1), post(2)]);
        await waitFor(() =>
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([input]) =>
                        urlOf(input) === "/api/v1/reactions/posts/?ids=1,2",
                ),
        );

        expect(container.querySelectorAll(".feed-entry")).toHaveLength(2);
        expect(container.textContent).toContain("Feed post 1");
        expect(container.textContent).toContain("Feed post 2");
        expect(container.querySelector(".feed-entry-reactions")).toBeNull();
        expect(container.querySelectorAll('[role="alert"]')).toHaveLength(0);

        act(() => {
            root.unmount();
        });
    });

    it("does not reserve a reaction surface for empty aggregates", async () => {
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                return Promise.resolve(response(signedIn));
            }
            if (url === "/api/v1/reactions/posts/?ids=1") {
                return Promise.resolve(
                    response({
                        results: [
                            {
                                post_id: 1,
                                slug: "привет-мир",
                                reactions: [],
                            },
                        ],
                    }),
                );
            }
            return Promise.reject(new Error(`Unexpected request: ${url}`));
        });

        const { container, root } = renderFeed([post(1)]);
        await waitFor(() =>
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([input]) =>
                        urlOf(input) === "/api/v1/reactions/posts/?ids=1",
                ),
        );

        expect(container.querySelector(".feed-entry-reactions")).toBeNull();
        expect(container.querySelector(".reaction-bar")).toBeNull();
        act(() => {
            root.unmount();
        });
    });

    it("does not cross the Draft Mode boundary", async () => {
        vi.mocked(fetch).mockImplementation((input) => {
            const url = urlOf(input);
            if (url === "/api/me/") {
                return Promise.resolve(response(signedIn));
            }
            return Promise.reject(new Error(`Unexpected request: ${url}`));
        });

        const { container, root } = renderFeed([post(1)], false);
        await waitFor(() =>
            vi
                .mocked(fetch)
                .mock.calls.some(([input]) => urlOf(input) === "/api/me/"),
        );

        expect(
            vi
                .mocked(fetch)
                .mock.calls.some(([input]) =>
                    urlOf(input).startsWith("/api/v1/reactions/posts/"),
                ),
        ).toBe(false);
        expect(container.querySelector(".feed-entry")).not.toBeNull();
        expect(container.querySelector(".reaction-bar")).toBeNull();
        act(() => {
            root.unmount();
        });
    });
});
