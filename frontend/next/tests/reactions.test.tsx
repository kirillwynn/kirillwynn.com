// @vitest-environment jsdom

import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/auth-provider";
import { CommentCard } from "@/components/comment-card";
import { PostReactions } from "@/components/post-reactions";
import { ReactionBar } from "@/components/reaction-bar";
import type { MeResponse } from "@/lib/auth";
import type { PublicComment } from "@/lib/comments";
import {
    clearPendingReaction,
    loadPendingReaction,
    loadRecentReactions,
    reactionStorageLimits,
    rememberReaction,
    savePendingReaction,
} from "@/lib/reaction-storage";
import {
    getReactionParticipants,
    resetReactionConfigForTests,
    toggleReaction,
    type ReactionGroup,
    type ReactionTarget,
} from "@/lib/reactions";

const anonymous: MeResponse = {
    authenticated: false,
    user: null,
    providers: {
        google: { available: true, connected: false },
        github: { available: true, connected: false },
    },
    csrf_token: "masked-csrf",
};

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

const postTarget: Extract<ReactionTarget, { kind: "post" }> = {
    kind: "post",
    id: 9,
    slug: "привет-мир",
    returnTo: "/posts/привет-мир",
};

function group(overrides: Partial<ReactionGroup> = {}): ReactionGroup {
    return {
        emoji: "🔥",
        count: 1,
        viewer_reacted: false,
        participants:
            "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/%F0%9F%94%A5/participants/",
        ...overrides,
    };
}

function comment(overrides: Partial<PublicComment> = {}): PublicComment {
    return {
        id: 7,
        kind: "comment",
        body: "Visible",
        status: "visible",
        author: {
            id: 3,
            display_name: "Author",
            is_site_author: false,
        },
        thread_root_id: null,
        reply_to: null,
        created_at: "2026-07-26T20:00:00Z",
        updated_at: "2026-07-26T20:00:00Z",
        edited_at: null,
        reply_count: 0,
        last_reply_at: null,
        reactions: [group()],
        viewer: {
            can_edit: false,
            can_delete: false,
            can_reply: true,
            can_react: true,
        },
        ...overrides,
    };
}

function response(
    payload: unknown,
    status = 200,
    extraHeaders?: HeadersInit,
): Response {
    const headers = new Headers(extraHeaders);
    headers.set("Content-Type", "application/json");
    return new Response(JSON.stringify(payload), { status, headers });
}

function urlOf(input: RequestInfo | URL): string {
    return typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
}

function defaultFetch(
    me: MeResponse,
    extra?: (url: string, options?: RequestInit) => Promise<Response> | null,
): void {
    vi.mocked(fetch).mockImplementation((input, options) => {
        const url = urlOf(input);
        const handled = extra?.(url, options);
        if (handled) {
            return handled;
        }
        if (url === "/api/me/") {
            return Promise.resolve(response(me));
        }
        if (url === "/api/v1/reactions/config/") {
            return Promise.resolve(
                response({ quick_reactions: ["👍", "❤️", "🎉"] }),
            );
        }
        return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
}

async function flush(): Promise<void> {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
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
    throw new Error("Timed out waiting for UI state.");
}

async function render(
    children: ReactNode,
): Promise<{ container: HTMLDivElement; root: Root }> {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(<AuthProvider>{children}</AuthProvider>);
    });
    await waitFor(
        () =>
            container.querySelector('[aria-label="Open full emoji picker"]') !==
            null,
    );
    return { container, root };
}

function inputValue(input: HTMLInputElement, value: string): void {
    // eslint-disable-next-line @typescript-eslint/unbound-method
    const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
    )?.set;
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

function buttonByLabel(
    container: ParentNode,
    label: string,
): HTMLButtonElement | undefined {
    return Array.from(
        container.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.getAttribute("aria-label") === label);
}

beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    window.sessionStorage.clear();
    window.localStorage.clear();
    resetReactionConfigForTests();
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    vi.unstubAllGlobals();
    document.body.replaceChildren();
});

describe("reaction API and local storage boundaries", () => {
    it("encodes Unicode slug and compound emoji once and sends session CSRF", async () => {
        vi.mocked(fetch).mockResolvedValueOnce(
            response({ action: "added", reactions: [] }),
        );

        await toggleReaction(postTarget, "👩‍💻", "csrf");

        expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
            "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/toggle/",
        );
        const options = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
        expect(options.credentials).toBe("same-origin");
        expect(options.cache).toBe("no-store");
        expect((options.headers as Headers).get("X-CSRFToken")).toBe("csrf");
        expect(JSON.parse(options.body as string)).toEqual({ emoji: "👩‍💻" });
    });

    it("rejects external and cross-reaction participant cursors", () => {
        expect(() =>
            getReactionParticipants(
                postTarget,
                "🔥",
                group().participants,
                "https://evil.example/cursor",
            ),
        ).toThrow("participants cursor is invalid");
        expect(() =>
            getReactionParticipants(
                postTarget,
                "🔥",
                "/api/v1/comments/7/reactions/%F0%9F%94%A5/participants/",
            ),
        ).toThrow("participants cursor is invalid");
        expect(fetch).not.toHaveBeenCalled();
    });

    it("bounds recent emoji and expires malformed pending OAuth intent", () => {
        for (let index = 0; index < 20; index += 1) {
            rememberReaction(index % 2 ? "🔥" : `🎉`);
        }
        expect(loadRecentReactions()).toEqual(["🔥", "🎉"]);

        localStorage.setItem(
            "kw:reaction-recent:v1",
            JSON.stringify(["🔥", "hello", ":custom:", 7, "🔥\u202e"]),
        );
        expect(loadRecentReactions()).toEqual(["🔥"]);

        savePendingReaction(postTarget, "👩‍💻", 100);
        expect(loadPendingReaction(postTarget, 101)).toBe("👩‍💻");
        expect(
            loadPendingReaction(
                postTarget,
                100 + reactionStorageLimits.intentTtlMs + 1,
            ),
        ).toBeNull();
        clearPendingReaction(postTarget, "👩‍💻");
    });
});

describe("post, comment, and reply reaction UI", () => {
    it("loads post pills, viewer highlight, and three quick reactions", async () => {
        defaultFetch(signedIn, (url) =>
            url.endsWith("/reactions/")
                ? Promise.resolve(
                      response({
                          reactions: [
                              group({ viewer_reacted: true, count: 2 }),
                          ],
                      }),
                  )
                : null,
        );
        const { container, root } = await render(
            <PostReactions id={9} slug="привет-мир" />,
        );

        expect(
            buttonByLabel(container, "Remove 🔥 reaction")?.getAttribute(
                "aria-pressed",
            ),
        ).toBe("true");
        expect(
            container.querySelectorAll('[aria-label^="React with"]').length,
        ).toBe(3);
        act(() => {
            root.unmount();
        });
    });

    it("renders pills for top-level comments and replies but not tombstones", async () => {
        defaultFetch(signedIn);
        const { container, root } = await render(
            <>
                <CommentCard
                    comment={comment()}
                    csrfToken="csrf"
                    onChange={() => undefined}
                    onReply={null}
                    onSessionExpired={() => undefined}
                    reactionReturnTo="/posts/привет"
                    slug="привет"
                />
                <CommentCard
                    comment={comment({
                        id: 8,
                        kind: "reply",
                        thread_root_id: 7,
                    })}
                    csrfToken="csrf"
                    onChange={() => undefined}
                    onReply={null}
                    onSessionExpired={() => undefined}
                    reactionReturnTo="/posts/привет?thread=7"
                    slug="привет"
                />
                <CommentCard
                    comment={comment({
                        id: 9,
                        body: null,
                        status: "deleted",
                        reactions: [],
                    })}
                    csrfToken="csrf"
                    onChange={() => undefined}
                    onReply={null}
                    onSessionExpired={() => undefined}
                    reactionReturnTo="/posts/привет"
                    slug="привет"
                />
            </>,
        );

        expect(
            Array.from(container.querySelectorAll('[aria-pressed="false"]')),
        ).toHaveLength(2);
        expect(
            container
                .querySelector('[data-comment-id="9"]')
                ?.querySelector(".reaction-bar"),
        ).toBeNull();
        act(() => {
            root.unmount();
        });
    });
});

describe("reaction mutation state", () => {
    it("updates optimistically, blocks double-click, and accepts authoritative state", async () => {
        let resolveToggle: ((value: Response) => void) | null = null;
        const pending = new Promise<Response>((resolve) => {
            resolveToggle = resolve;
        });
        defaultFetch(signedIn, (url, options) =>
            options?.method === "POST" && url.includes("/toggle/")
                ? pending
                : null,
        );
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        const add = buttonByLabel(container, "Add 🔥 reaction");
        act(() => {
            add?.click();
            add?.click();
        });
        expect(buttonByLabel(container, "Remove 🔥 reaction")).toBeDefined();
        expect(
            vi
                .mocked(fetch)
                .mock.calls.filter((call) => call[1]?.method === "POST"),
        ).toHaveLength(1);
        expect(buttonByLabel(container, "Remove 🔥 reaction")?.disabled).toBe(
            true,
        );

        await act(async () => {
            resolveToggle?.(
                response({
                    action: "added",
                    reactions: [group({ count: 3, viewer_reacted: true })],
                }),
            );
            await pending;
        });
        expect(
            buttonByLabel(container, "View 3 participants for 🔥"),
        ).toBeDefined();
        act(() => {
            root.unmount();
        });
    });

    it("rolls back network errors and reports 429 Retry-After", async () => {
        defaultFetch(signedIn, (url, options) => {
            if (options?.method !== "POST" || !url.includes("/toggle/")) {
                return null;
            }
            return vi
                .mocked(fetch)
                .mock.calls.filter((call) => call[1]?.method === "POST")
                .length === 1
                ? Promise.reject(new Error("offline"))
                : Promise.resolve(
                      response({ detail: "Too many reaction toggles." }, 429, {
                          "Retry-After": "19",
                      }),
                  );
        });
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(container, "Add 🔥 reaction")?.click();
        });
        await flush();
        expect(buttonByLabel(container, "Add 🔥 reaction")).toBeDefined();
        expect(container.textContent).toContain("previous state was restored");

        act(() => {
            buttonByLabel(container, "Add 🔥 reaction")?.click();
        });
        await flush();
        expect(container.textContent).toContain("Retry in about 19 seconds");
        act(() => {
            root.unmount();
        });
    });

    it("refreshes auth and rolls back when the session expires", async () => {
        let meCalls = 0;
        defaultFetch(signedIn, (url, options) => {
            if (url === "/api/me/") {
                meCalls += 1;
                return Promise.resolve(response(signedIn));
            }
            return options?.method === "POST" && url.includes("/toggle/")
                ? Promise.resolve(response({ detail: "Forbidden" }, 403))
                : null;
        });
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(container, "Add 🔥 reaction")?.click();
        });
        await flush();
        expect(meCalls).toBe(2);
        expect(container.textContent).toContain("session expired");
        expect(buttonByLabel(container, "Add 🔥 reaction")).toBeDefined();
        act(() => {
            root.unmount();
        });
    });
});

describe("participants, picker, and OAuth continuation", () => {
    it("opens minimal participants on focus and mobile count tap", async () => {
        defaultFetch(signedIn, (url) =>
            url.includes("/participants/")
                ? Promise.resolve(
                      response({
                          next: null,
                          previous: null,
                          results: [
                              {
                                  id: 1,
                                  display_name: "Kirill",
                                  is_site_author: true,
                              },
                          ],
                      }),
                  )
                : null,
        );
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(container, "Add 🔥 reaction")?.focus();
        });
        await flush();
        expect(container.textContent).toContain("Kirill · Author");
        act(() => {
            container
                .querySelector<HTMLButtonElement>(
                    '[aria-label="Close reaction participants"]',
                )
                ?.click();
        });
        await flush();
        act(() => {
            buttonByLabel(container, "View 1 participant for 🔥")?.click();
        });
        await waitFor(() =>
            Array.from(container.querySelectorAll('[role="dialog"]')).some(
                (dialog) =>
                    dialog.getAttribute("aria-label") ===
                    "🔥 reaction participants",
            ),
        );
        expect(
            Array.from(container.querySelectorAll('[role="dialog"]')).find(
                (dialog) =>
                    dialog.getAttribute("aria-label") ===
                    "🔥 reaction participants",
            ),
        ).toBeDefined();
        act(() => {
            root.unmount();
        });
    });

    it("lazy-loads searchable picker, recent emoji, arrows, and Escape", async () => {
        rememberReaction("🔥");
        defaultFetch(signedIn);
        const { container, root } = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        act(() => {
            container
                .querySelector<HTMLButtonElement>(
                    '[aria-label="Open full emoji picker"]',
                )
                ?.click();
        });
        await waitFor(
            () =>
                container.querySelector<HTMLInputElement>(
                    'input[placeholder="Search emoji"]',
                ) !== null,
        );
        expect(buttonByLabel(container, "React with 🔥")).toBeDefined();
        const search = container.querySelector<HTMLInputElement>(
            'input[placeholder="Search emoji"]',
        );
        act(() => {
            if (search) {
                inputValue(search, "rocket");
            }
        });
        await waitFor(
            () =>
                container.querySelector<HTMLButtonElement>(
                    '[aria-label="Rocket"]',
                ) !== null,
        );
        const rocket = container.querySelector<HTMLButtonElement>(
            '[aria-label="Rocket"]',
        );
        expect(rocket).not.toBeNull();
        const gridButtons = container.querySelectorAll<HTMLButtonElement>(
            '[role="grid"] button',
        );
        act(() => {
            gridButtons[0].focus();
            gridButtons[0].dispatchEvent(
                new KeyboardEvent("keydown", {
                    key: "ArrowRight",
                    bubbles: true,
                }),
            );
        });
        expect(document.activeElement).toBe(gridButtons[1]);
        act(() => {
            container
                .querySelector('[aria-label="Choose an emoji"]')
                ?.dispatchEvent(
                    new KeyboardEvent("keydown", {
                        key: "Escape",
                        bubbles: true,
                    }),
                );
        });
        expect(
            container.querySelector('[aria-label="Choose an emoji"]'),
        ).toBeNull();
        act(() => {
            root.unmount();
        });
    });

    it("restores Unicode pending intent after OAuth but waits for confirmation", async () => {
        defaultFetch(anonymous);
        const anonymousRender = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(anonymousRender.container, "React with 👍")?.click();
        });
        const login =
            anonymousRender.container.querySelector<HTMLAnchorElement>(
                'a[href^="/login?next="]',
            );
        expect(login?.href).toContain(
            "next=%2Fposts%2F%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80",
        );
        expect(loadPendingReaction(postTarget)).toBe("👍");
        act(() => {
            anonymousRender.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        let postCalls = 0;
        defaultFetch(signedIn, (url, options) => {
            if (options?.method === "POST" && url.includes("/toggle/")) {
                postCalls += 1;
                return Promise.resolve(
                    response({
                        action: "added",
                        reactions: [
                            group({
                                emoji: "👍",
                                viewer_reacted: true,
                                participants:
                                    "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/%F0%9F%91%8D/participants/",
                            }),
                        ],
                    }),
                );
            }
            return null;
        });
        const authenticatedRender = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        expect(postCalls).toBe(0);
        expect(authenticatedRender.container.textContent).toContain(
            "Add your saved 👍 reaction?",
        );
        act(() => {
            Array.from(authenticatedRender.container.querySelectorAll("button"))
                .find((button) => button.textContent === "Confirm")
                ?.click();
        });
        await flush();
        expect(postCalls).toBe(1);
        expect(loadPendingReaction(postTarget)).toBeNull();
        act(() => {
            authenticatedRender.root.unmount();
        });
    });
});
