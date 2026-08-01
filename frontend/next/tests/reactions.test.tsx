// @vitest-environment jsdom

import { act, type ReactNode, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/auth-provider";
import { CommentCard } from "@/components/comment-card";
import { PostReactions } from "@/components/post-reactions";
import { ReactionBar } from "@/components/reaction-bar";
import { ReactionImage } from "@/components/reaction-image";
import type { MeResponse } from "@/lib/auth";
import { applyCommentReactionChange } from "@/lib/comment-reconciliation";
import type { PublicComment } from "@/lib/comments";
import { resetReactionMutationCoordinatorForTests } from "@/lib/reaction-mutation-coordinator";
import {
    clearPendingReaction,
    isValidReactionId,
    loadPendingReaction,
    loadRecentReactions,
    reactionStorageLimits,
    rememberReaction,
    savePendingReaction,
} from "@/lib/reaction-storage";
import {
    getReactionParticipants,
    resetReactionCatalogForTests,
    toggleReaction,
    type ReactionChange,
    type ReactionDescriptor,
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
        nickname: "Reader",
        display_name: "Reader",
        nickname_suggestion: null,
        email: "reader@example.com",
        email_verified: true,
        profile_complete: true,
        has_usable_password: true,
        nickname_change_available_at: null,
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

const commentTarget: Extract<ReactionTarget, { kind: "comment" }> = {
    kind: "comment",
    id: 7,
    slug: "привет-мир",
    returnTo: "/posts/привет-мир?thread=7",
};

const clap: ReactionDescriptor = {
    id: "pepeclap",
    name: "Pepe clap",
    label: "Clapping",
    kind: "animated",
    asset_url: "/media/reactions/pepeclap/hash/animation.gif",
    poster_url: "/media/reactions/pepeclap/hash/poster.webp",
    width: 64,
    height: 64,
    version: "sha256-clap",
};

const hmm: ReactionDescriptor = {
    id: "pepehmm",
    name: "Pepe hmm",
    label: "Thinking",
    kind: "static",
    asset_url: "/media/reactions/pepehmm/hash/asset.webp",
    poster_url: "/media/reactions/pepehmm/hash/asset.webp",
    width: 64,
    height: 64,
    version: "sha256-hmm",
};

const love: ReactionDescriptor = {
    id: "pepelove",
    name: "Pepe love",
    label: "Sending love",
    kind: "static",
    asset_url: "/media/reactions/pepelove/hash/asset.webp",
    poster_url: "/media/reactions/pepelove/hash/asset.webp",
    width: 64,
    height: 64,
    version: "sha256-love",
};

const rocket: ReactionDescriptor = {
    id: "peperocket",
    name: "Pepe rocket",
    label: "Launching a rocket",
    kind: "animated",
    asset_url: "/media/reactions/peperocket/hash/animation.gif",
    poster_url: "/media/reactions/peperocket/hash/poster.webp",
    width: 64,
    height: 64,
    version: "sha256-rocket",
};

const partyReaction: ReactionDescriptor = {
    id: "pepeparty",
    name: "Pepe party",
    label: "Celebrating",
    kind: "static",
    asset_url: "/media/reactions/pepeparty/hash/asset.webp",
    poster_url: "/media/reactions/pepeparty/hash/asset.webp",
    width: 64,
    height: 64,
    version: "sha256-party",
};

function group(overrides: Partial<ReactionGroup> = {}): ReactionGroup {
    return {
        reaction: clap,
        count: 1,
        viewer_reacted: false,
        participants:
            "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/pepeclap/participants/",
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
        if (url === "/api/v1/reactions/catalog/") {
            return Promise.resolve(
                response({
                    version: "sha256-test",
                    results: [clap, hmm, love, partyReaction, rocket],
                }),
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
            container.querySelector('[aria-label="Choose reaction"]') !== null,
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

function deferred<T>(): {
    promise: Promise<T>;
    reject: (reason?: unknown) => void;
    resolve: (value: T) => void;
} {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, reject, resolve };
}

function pointerEvent(type: string, pointerType: string): Event {
    const event = new MouseEvent(type, { bubbles: true });
    Object.defineProperty(event, "pointerType", { value: pointerType });
    return event;
}

function DuplicateReactionBars({
    onMutation,
    target = commentTarget,
}: {
    onMutation: (change: ReactionChange) => void;
    target?: ReactionTarget;
}) {
    const [parent, setParent] = useState(
        comment({
            reactions: [
                group({
                    participants:
                        "/api/v1/comments/7/reactions/pepeclap/participants/",
                }),
            ],
        }),
    );

    function change(changeEvent: ReactionChange): void {
        onMutation(changeEvent);
        setParent((current) =>
            applyCommentReactionChange(current, changeEvent),
        );
    }

    return (
        <>
            <output
                data-count={parent.reactions[0]?.count ?? 0}
                data-pending={
                    parent.reaction_pending_revision === undefined
                        ? "none"
                        : String(parent.reaction_pending_revision)
                }
                data-viewer-reacted={
                    parent.reactions[0]?.viewer_reacted ?? false
                }
            />
            {["list", "thread"].map((instance) => (
                <div data-instance={instance} key={instance}>
                    <ReactionBar
                        initialReactions={parent.reactions}
                        onChange={change}
                        target={target}
                    />
                </div>
            ))}
        </>
    );
}

beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal(
        "matchMedia",
        vi.fn().mockReturnValue({
            matches: false,
            media: "",
            onchange: null,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
            addListener: vi.fn(),
            removeListener: vi.fn(),
            dispatchEvent: vi.fn(),
        } satisfies MediaQueryList),
    );
    window.sessionStorage.clear();
    window.localStorage.clear();
    resetReactionCatalogForTests();
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

describe("reaction API and local storage boundaries", () => {
    it("encodes the Unicode slug once and sends only a catalog ID with session CSRF", async () => {
        vi.mocked(fetch).mockResolvedValueOnce(
            response({ action: "added", reactions: [] }),
        );

        await toggleReaction(postTarget, clap.id, "csrf");

        expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
            "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/toggle/",
        );
        const options = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
        expect(options.credentials).toBe("same-origin");
        expect(options.cache).toBe("no-store");
        expect((options.headers as Headers).get("X-CSRFToken")).toBe("csrf");
        expect(JSON.parse(options.body as string) as unknown).toEqual({
            reaction_id: clap.id,
        });
    });

    it("rejects external and cross-reaction participant cursors", () => {
        expect(() =>
            getReactionParticipants(
                postTarget,
                clap.id,
                group().participants,
                "https://evil.example/cursor",
            ),
        ).toThrow("participants cursor is invalid");
        expect(() =>
            getReactionParticipants(
                postTarget,
                clap.id,
                "/api/v1/comments/7/reactions/pepeclap/participants/",
            ),
        ).toThrow("participants cursor is invalid");
        expect(fetch).not.toHaveBeenCalled();
    });

    it("strictly validates versioned catalog-ID storage and clears Unicode v1 entries", () => {
        for (let index = 0; index < 20; index += 1) {
            rememberReaction(index % 2 ? clap.id : hmm.id);
        }
        expect(loadRecentReactions()).toEqual([clap.id, hmm.id]);

        localStorage.setItem(
            "kw:reaction-recent:v2",
            JSON.stringify({
                version: 2,
                reactionIds: [
                    clap.id,
                    "🔥",
                    "PepeClap",
                    "pepeclap.png",
                    "https://media.example/reaction.gif",
                    7,
                ],
            }),
        );
        expect(loadRecentReactions()).toEqual([clap.id]);

        for (const malformed of [
            "🔥",
            ":pepeclap:",
            "pepeclap.png",
            "PepeClap",
            "../pepeclap",
            "https://media.example/reaction.gif",
        ]) {
            expect(isValidReactionId(malformed)).toBe(false);
            savePendingReaction(postTarget, malformed, 90);
            expect(loadPendingReaction(postTarget, 91)).toBeNull();
        }

        const pendingKey =
            "kw:reaction-intent:v3:pending-auth:%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80:post:9:pepeclap";
        for (const malformedJson of [
            "null",
            "[]",
            "{}",
            '{"version":3,"reactionId":"🔥","createdAt":90}',
            '{"version":3,"reactionId":"pepeclap","createdAt":"90"}',
            '{"version":2,"reactionId":"pepeclap","createdAt":90}',
        ]) {
            sessionStorage.setItem(pendingKey, malformedJson);
            expect(loadPendingReaction(postTarget, 91)).toBeNull();
            expect(sessionStorage.getItem(pendingKey)).toBeNull();
        }

        localStorage.removeItem("kw:reaction-recent:v2");
        localStorage.setItem("kw:reaction-recent:v1", JSON.stringify(["🔥"]));
        sessionStorage.setItem(
            "kw:reaction-intent:v1:%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80:post:9:%F0%9F%94%A5",
            JSON.stringify({ emoji: "🔥", createdAt: 90 }),
        );
        expect(loadRecentReactions()).toEqual([]);
        expect(loadPendingReaction(postTarget, 91)).toBeNull();
        expect(localStorage.getItem("kw:reaction-recent:v1")).toBeNull();
        expect(sessionStorage.length).toBe(0);
    });

    it("keeps one newest pending intent per target and clears the whole target", () => {
        const otherTarget: ReactionTarget = {
            ...postTarget,
            id: 10,
        };
        savePendingReaction(otherTarget, love.id, 50);
        savePendingReaction(postTarget, clap.id, 100);
        savePendingReaction(postTarget, hmm.id, 200);

        expect(loadPendingReaction(postTarget, 201)).toBe(hmm.id);
        expect(loadPendingReaction(otherTarget, 201)).toBe(love.id);
        expect(
            Array.from({ length: sessionStorage.length }, (_, index) =>
                sessionStorage.key(index),
            ).filter((key) => key?.includes(":post:9:")),
        ).toHaveLength(1);

        clearPendingReaction(postTarget);
        expect(loadPendingReaction(postTarget, 202)).toBeNull();
        expect(loadPendingReaction(otherTarget, 202)).toBe(love.id);
    });

    it("chooses duplicate v3 intents by createdAt and preserves TTL", () => {
        const prefix =
            "kw:reaction-intent:v3:pending-auth:%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80:post:9:";
        sessionStorage.setItem(
            `${prefix}${hmm.id}`,
            JSON.stringify({
                version: 3,
                reactionId: hmm.id,
                createdAt: 200,
            }),
        );
        sessionStorage.setItem(
            `${prefix}${clap.id}`,
            JSON.stringify({
                version: 3,
                reactionId: clap.id,
                createdAt: 100,
            }),
        );

        expect(loadPendingReaction(postTarget, 201)).toBe(hmm.id);
        expect(sessionStorage.length).toBe(1);
        expect(
            loadPendingReaction(
                postTarget,
                200 + reactionStorageLimits.intentTtlMs + 1,
            ),
        ).toBeNull();
    });

    it("adopts an anonymous intent into one user namespace without leaking it", () => {
        savePendingReaction(postTarget, clap.id, 100);

        expect(loadPendingReaction(postTarget, 101, 42)).toBe(clap.id);
        expect(loadPendingReaction(postTarget, 101)).toBeNull();
        expect(loadPendingReaction(postTarget, 101, 7)).toBeNull();

        savePendingReaction(postTarget, hmm.id, 102, 7);
        expect(loadPendingReaction(postTarget, 103, 42)).toBe(clap.id);
        expect(loadPendingReaction(postTarget, 103, 7)).toBe(hmm.id);

        clearPendingReaction(postTarget, 42);
        expect(loadPendingReaction(postTarget, 104, 42)).toBeNull();
        expect(loadPendingReaction(postTarget, 104, 7)).toBe(hmm.id);
    });
});

describe("reaction asset loading boundaries", () => {
    it("uses static assets and falls back from a broken animation to poster and text", async () => {
        const container = document.createElement("div");
        document.body.append(container);
        const root = createRoot(container);
        act(() => {
            root.render(
                <>
                    <button aria-label="Clapping" type="button">
                        <ReactionImage reaction={clap} />
                    </button>
                    <button aria-label="Thinking" type="button">
                        <ReactionImage reaction={hmm} />
                    </button>
                </>,
            );
        });
        await flush();

        const images = container.querySelectorAll("img");
        expect(images[0].getAttribute("src")).toBe(clap.asset_url);
        expect(images[0].getAttribute("alt")).toBe("");
        expect(images[1].getAttribute("src")).toBe(hmm.asset_url);

        act(() => {
            images[0].dispatchEvent(new Event("error", { bubbles: true }));
        });
        await flush();
        const poster = container.querySelectorAll("img")[0];
        expect(poster.getAttribute("src")).toBe(clap.poster_url);
        act(() => {
            poster.dispatchEvent(new Event("error", { bubbles: true }));
        });
        await flush();
        expect(container.textContent).toContain(clap.name);

        act(() => {
            root.unmount();
        });
    });

    it("never selects an animation URL in reduced motion", async () => {
        vi.mocked(matchMedia).mockReturnValue({
            matches: true,
            media: "(prefers-reduced-motion: reduce)",
            onchange: null,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
            addListener: vi.fn(),
            removeListener: vi.fn(),
            dispatchEvent: vi.fn(),
        });
        const container = document.createElement("div");
        document.body.append(container);
        const root = createRoot(container);
        act(() => {
            root.render(
                <button aria-label="Clapping" type="button">
                    <ReactionImage reaction={clap} />
                </button>,
            );
        });
        await flush();

        const image = container.querySelector("img");
        expect(image?.getAttribute("src")).toBe(clap.poster_url);
        expect(container.innerHTML).not.toContain(clap.asset_url);

        act(() => {
            root.unmount();
        });
    });

    it("defers picker assets until intersecting and removes them offscreen", async () => {
        let observerCallback: IntersectionObserverCallback | null = null;
        let observerOptions: IntersectionObserverInit | undefined;
        class TestIntersectionObserver implements IntersectionObserver {
            readonly root = null;
            readonly rootMargin = "0px";
            readonly thresholds = [0];

            constructor(
                callback: IntersectionObserverCallback,
                options?: IntersectionObserverInit,
            ) {
                observerCallback = callback;
                observerOptions = options;
            }

            disconnect = vi.fn();
            observe = vi.fn();
            takeRecords(): IntersectionObserverEntry[] {
                return [];
            }
            unobserve = vi.fn();
        }
        vi.stubGlobal("IntersectionObserver", TestIntersectionObserver);
        const container = document.createElement("div");
        document.body.append(container);
        const root = createRoot(container);
        act(() => {
            root.render(
                <button aria-label="Clapping" type="button">
                    <ReactionImage deferUntilVisible reaction={clap} />
                </button>,
            );
        });
        await flush();
        expect(observerOptions?.rootMargin).toBe("0px");
        expect(container.querySelector("img")).toBeNull();

        act(() => {
            observerCallback?.(
                [{ isIntersecting: true } as IntersectionObserverEntry],
                {} as IntersectionObserver,
            );
        });
        expect(container.querySelector("img")?.getAttribute("src")).toBe(
            clap.asset_url,
        );
        act(() => {
            observerCallback?.(
                [{ isIntersecting: false } as IntersectionObserverEntry],
                {} as IntersectionObserver,
            );
        });
        expect(container.querySelector("img")).toBeNull();

        act(() => {
            root.unmount();
        });
    });
});

describe("post, comment, and reply reaction UI", () => {
    it("shows exactly one picker trigger for a post without aggregates and preloads nothing", async () => {
        defaultFetch(signedIn, (url) =>
            url.endsWith("/reactions/")
                ? Promise.resolve(response({ reactions: [] }))
                : null,
        );
        const { container, root } = await render(
            <PostReactions id={9} slug="привет-мир" />,
        );

        const group = container.querySelector(
            '[role="group"][aria-label="Reactions"]',
        );
        expect(group?.querySelectorAll("button")).toHaveLength(1);
        expect(
            buttonByLabel(group ?? container, "Choose reaction"),
        ).toBeDefined();
        expect(group?.querySelector("img")).toBeNull();
        expect(container.textContent).not.toContain(
            "Quick reactions could not be loaded",
        );
        const requested = vi
            .mocked(fetch)
            .mock.calls.map(([input]) => urlOf(input));
        expect(requested).not.toContain("/api/v1/reactions/config/");
        expect(requested).not.toContain("/api/v1/reactions/catalog/");
        act(() => {
            root.unmount();
        });
    });

    it("shows aggregates as ordinary pills plus exactly one picker trigger", async () => {
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
            buttonByLabel(container, "Remove Clapping reaction")?.getAttribute(
                "aria-pressed",
            ),
        ).toBe("true");
        expect(
            container.querySelectorAll('[aria-label^="React with"]'),
        ).toHaveLength(0);
        expect(buttonByLabel(container, "Choose reaction")).toBeDefined();
        expect(
            container.querySelectorAll('button[aria-label="Choose reaction"]'),
        ).toHaveLength(1);
        expect(container.querySelectorAll(".reaction-pill")).toHaveLength(1);
        expect(container.innerHTML).not.toContain(hmm.asset_url);
        expect(container.innerHTML).not.toContain(love.asset_url);
        expect(
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([input]) =>
                        urlOf(input) === "/api/v1/reactions/config/" ||
                        urlOf(input) === "/api/v1/reactions/catalog/",
                ),
        ).toBe(false);
        expect(
            container.querySelector(
                ".post-reactions .reaction-bar-slack-pills",
            ),
        ).not.toBeNull();
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
            container.querySelectorAll('button[aria-label="Choose reaction"]'),
        ).toHaveLength(2);
        expect(
            container.querySelectorAll('[aria-label^="React with"]'),
        ).toHaveLength(0);
        expect(
            container
                .querySelector('[data-comment-id="9"]')
                ?.querySelector(".reaction-bar"),
        ).toBeNull();
        expect(
            container.querySelector(
                '[data-comment-id="7"] .reaction-bar-slack-pills',
            ),
        ).toBeNull();
        act(() => {
            root.unmount();
        });
    });
});

describe("reaction mutation state", () => {
    it("updates optimistically, blocks double-click, and accepts authoritative state", async () => {
        let resolveToggle: ((value: Response) => void) | null = null;
        const changes: Array<{
            revision: number;
            source: string;
        }> = [];
        const pending = new Promise<Response>((resolve) => {
            resolveToggle = resolve;
        });
        defaultFetch(signedIn, (url, options) =>
            options?.method === "POST" && url.includes("/toggle/")
                ? pending
                : null,
        );
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[group()]}
                onChange={(change) => {
                    changes.push({
                        revision: change.revision,
                        source: change.source,
                    });
                }}
                target={postTarget}
            />,
        );
        const add = buttonByLabel(container, "Add Clapping reaction");
        act(() => {
            add?.click();
            add?.click();
        });
        expect(
            buttonByLabel(container, "Remove Clapping reaction"),
        ).toBeDefined();
        expect(
            vi
                .mocked(fetch)
                .mock.calls.filter((call) => call[1]?.method === "POST"),
        ).toHaveLength(1);
        expect(
            buttonByLabel(container, "Remove Clapping reaction")?.disabled,
        ).toBe(true);

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
            buttonByLabel(container, "View 3 participants for Clapping"),
        ).toBeDefined();
        expect(changes.map((change) => change.source)).toEqual([
            "optimistic",
            "authoritative",
        ]);
        expect(changes[0]?.revision).toBe(changes[1]?.revision);
        act(() => {
            root.unmount();
        });
    });

    it("rolls back network errors and reports 429 Retry-After", async () => {
        const sources: string[] = [];
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
            <ReactionBar
                initialReactions={[group()]}
                onChange={(change) => {
                    sources.push(change.source);
                }}
                target={postTarget}
            />,
        );
        act(() => {
            buttonByLabel(container, "Add Clapping reaction")?.click();
        });
        await flush();
        expect(buttonByLabel(container, "Add Clapping reaction")).toBeDefined();
        expect(container.textContent).toContain("previous state was restored");
        expect(sources.slice(0, 2)).toEqual(["optimistic", "rollback"]);

        act(() => {
            buttonByLabel(container, "Add Clapping reaction")?.click();
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
            buttonByLabel(container, "Add Clapping reaction")?.click();
        });
        await flush();
        expect(meCalls).toBe(2);
        expect(container.textContent).toContain("session expired");
        expect(buttonByLabel(container, "Add Clapping reaction")).toBeDefined();
        expect(loadPendingReaction(postTarget, Date.now(), 42)).toBe(clap.id);
        expect(loadPendingReaction(postTarget, Date.now(), 7)).toBeNull();
        act(() => {
            root.unmount();
        });
    });

    it("coordinates duplicate comment instances through one shared mutation owner", async () => {
        const firstToggle = deferred<Response>();
        const secondToggle = deferred<Response>();
        const changes: ReactionChange[] = [];
        let toggleCalls = 0;
        defaultFetch(signedIn, (url, options) => {
            if (options?.method !== "POST" || !url.includes("/toggle/")) {
                return null;
            }
            const pending = toggleCalls === 0 ? firstToggle : secondToggle;
            toggleCalls += 1;
            return pending.promise;
        });
        const { container, root } = await render(
            <DuplicateReactionBars
                onMutation={(change) => {
                    changes.push(change);
                }}
            />,
        );
        const first = container.querySelector('[data-instance="list"]');
        const second = container.querySelector('[data-instance="thread"]');

        act(() => {
            buttonByLabel(first ?? container, "Add Clapping reaction")?.click();
        });
        await flush();
        expect(
            container.querySelector("output")?.getAttribute("data-pending"),
        ).not.toBe("none");
        expect(
            buttonByLabel(second ?? container, "Remove Clapping reaction")
                ?.disabled,
        ).toBe(true);
        act(() => {
            buttonByLabel(
                second ?? container,
                "Remove Clapping reaction",
            )?.click();
        });
        expect(toggleCalls).toBe(1);

        await act(async () => {
            firstToggle.resolve(
                response({
                    action: "added",
                    reactions: [group({ count: 4, viewer_reacted: true })],
                }),
            );
            await firstToggle.promise;
        });
        await flush();
        expect(
            container.querySelector("output")?.getAttribute("data-count"),
        ).toBe("4");
        expect(
            container.querySelector("output")?.getAttribute("data-pending"),
        ).toBe("none");
        expect(
            container
                .querySelector("output")
                ?.getAttribute("data-viewer-reacted"),
        ).toBe("true");

        act(() => {
            buttonByLabel(
                second ?? container,
                "Remove Clapping reaction",
            )?.click();
        });
        expect(toggleCalls).toBe(2);
        await act(async () => {
            secondToggle.resolve(
                response({
                    action: "removed",
                    reactions: [group({ count: 3, viewer_reacted: false })],
                }),
            );
            await secondToggle.promise;
        });
        await flush();

        const optimisticRevisions = changes
            .filter((change) => change.source === "optimistic")
            .map((change) => change.revision);
        expect(new Set(optimisticRevisions).size).toBe(2);
        expect(optimisticRevisions[0]).not.toBe(optimisticRevisions.at(-1));
        expect(
            container.querySelector("output")?.getAttribute("data-count"),
        ).toBe("3");
        expect(
            container.querySelector("output")?.getAttribute("data-pending"),
        ).toBe("none");
        expect(
            buttonByLabel(first ?? container, "Add Clapping reaction"),
        ).toBeDefined();
        expect(
            buttonByLabel(second ?? container, "Add Clapping reaction"),
        ).toBeDefined();
        act(() => {
            root.unmount();
        });
    });

    it("does not let one pending target block or overwrite another target", async () => {
        const pendingPost = deferred<Response>();
        const otherTarget: ReactionTarget = {
            kind: "comment",
            id: 88,
            slug: "привет-мир",
            returnTo: "/posts/привет-мир?thread=88",
        };
        defaultFetch(signedIn, (url, options) => {
            if (options?.method !== "POST" || !url.includes("/toggle/")) {
                return null;
            }
            return url.includes("/posts/")
                ? pendingPost.promise
                : Promise.resolve(
                      response({
                          action: "added",
                          reactions: [
                              group({ count: 8, viewer_reacted: true }),
                          ],
                      }),
                  );
        });
        const { container, root } = await render(
            <>
                <div data-target="post">
                    <ReactionBar
                        initialReactions={[group()]}
                        target={postTarget}
                    />
                </div>
                <div data-target="comment">
                    <ReactionBar
                        initialReactions={[group()]}
                        target={otherTarget}
                    />
                </div>
            </>,
        );
        const post = container.querySelector('[data-target="post"]');
        const other = container.querySelector('[data-target="comment"]');
        act(() => {
            buttonByLabel(post ?? container, "Add Clapping reaction")?.click();
            buttonByLabel(other ?? container, "Add Clapping reaction")?.click();
        });
        await flush();
        expect(
            vi
                .mocked(fetch)
                .mock.calls.filter((call) => call[1]?.method === "POST"),
        ).toHaveLength(2);
        expect(
            buttonByLabel(
                other ?? container,
                "View 8 participants for Clapping",
            ),
        ).toBeDefined();
        expect(
            buttonByLabel(post ?? container, "Remove Clapping reaction")
                ?.disabled,
        ).toBe(true);

        await act(async () => {
            pendingPost.resolve(
                response({
                    action: "added",
                    reactions: [group({ count: 5, viewer_reacted: true })],
                }),
            );
            await pendingPost.promise;
        });
        await flush();
        expect(
            buttonByLabel(
                post ?? container,
                "View 5 participants for Clapping",
            ),
        ).toBeDefined();
        expect(
            buttonByLabel(
                other ?? container,
                "View 8 participants for Clapping",
            ),
        ).toBeDefined();
        act(() => {
            root.unmount();
        });
    });
});

describe("participants, picker, and OAuth continuation", () => {
    it("keeps reaction accessibility labels singular", async () => {
        const labeledReaction = {
            ...clap,
            label: "Clapping reaction",
        };
        defaultFetch(signedIn);
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[
                    group({
                        reaction: labeledReaction,
                    }),
                ]}
                target={postTarget}
            />,
        );

        expect(buttonByLabel(container, "Add Clapping reaction")).toBeDefined();
        expect(container.innerHTML).not.toContain("reaction reaction");
        act(() => {
            buttonByLabel(container, "Add Clapping reaction")?.focus();
        });
        await flush();
        expect(
            container.querySelector(
                '[aria-label="Clapping reaction participants"]',
            ),
        ).not.toBeNull();
        expect(container.innerHTML).not.toContain("reaction reaction");

        act(() => {
            root.unmount();
        });
    });

    it("closes an open participant view when a mutation changes reactions", async () => {
        defaultFetch(signedIn, (url, options) => {
            if (url.includes("/participants/")) {
                return Promise.resolve(
                    response({
                        next: null,
                        previous: null,
                        results: [],
                    }),
                );
            }
            if (options?.method === "POST" && url.includes("/toggle/")) {
                return Promise.resolve(
                    response({
                        action: "removed",
                        reactions: [],
                    }),
                );
            }
            return null;
        });
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[
                    group({
                        count: 1,
                        viewer_reacted: true,
                    }),
                ]}
                target={postTarget}
            />,
        );
        const toggle = buttonByLabel(container, "Remove Clapping reaction");
        act(() => {
            toggle?.focus();
        });
        await waitFor(
            () =>
                container.querySelector(
                    '[aria-label="Clapping reaction participants"]',
                ) !== null,
        );
        act(() => {
            toggle?.click();
        });
        await waitFor(
            () =>
                container.querySelector(
                    '[aria-label="Clapping reaction participants"]',
                ) === null,
        );
        expect(buttonByLabel(container, "Choose reaction")).toBeDefined();
        expect(container.querySelector(".reaction-pill")).toBeNull();

        act(() => {
            root.unmount();
        });
    });

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
            buttonByLabel(container, "Add Clapping reaction")?.focus();
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
        const countTrigger = buttonByLabel(
            container,
            "View 1 participant for Clapping",
        );
        act(() => {
            countTrigger?.click();
        });
        await waitFor(() =>
            Array.from(container.querySelectorAll('[role="dialog"]')).some(
                (dialog) =>
                    dialog.getAttribute("aria-label") ===
                    "Clapping reaction participants",
            ),
        );
        expect(
            Array.from(container.querySelectorAll('[role="dialog"]')).find(
                (dialog) =>
                    dialog.getAttribute("aria-label") ===
                    "Clapping reaction participants",
            ),
        ).toBeDefined();
        act(() => {
            document.dispatchEvent(
                new KeyboardEvent("keydown", {
                    key: "Escape",
                    bubbles: true,
                }),
            );
        });
        expect(
            container.querySelector(
                '[aria-label="Clapping reaction participants"]',
            ),
        ).toBeNull();
        expect(document.activeElement).toBe(countTrigger);
        act(() => {
            root.unmount();
        });
    });

    it("ignores stale participant success and error responses after switching reactions", async () => {
        const fire = deferred<Response>();
        const party = deferred<Response>();
        defaultFetch(signedIn, (url) => {
            if (url.includes("/pepeclap/participants/")) {
                return fire.promise;
            }
            if (url.includes("/pepeparty/participants/")) {
                return party.promise;
            }
            return null;
        });
        const partyGroup = group({
            reaction: partyReaction,
            participants:
                "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/pepeparty/participants/",
        });
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[group(), partyGroup]}
                target={postTarget}
            />,
        );

        act(() => {
            buttonByLabel(container, "Add Clapping reaction")?.focus();
        });
        await flush();
        act(() => {
            buttonByLabel(container, "Add Celebrating reaction")?.focus();
        });
        await flush();
        expect(
            vi
                .mocked(fetch)
                .mock.calls.map((call) => urlOf(call[0]))
                .filter((url) => url.includes("/participants/")),
        ).toEqual([group().participants, partyGroup.participants]);
        await act(async () => {
            party.resolve(
                response({
                    next: null,
                    previous: null,
                    results: [
                        {
                            id: 2,
                            display_name: "Party participant",
                            is_site_author: false,
                        },
                    ],
                }),
            );
            await party.promise;
        });
        await flush();
        expect(container.textContent).toContain("Party participant");
        expect(
            Array.from(
                container.querySelectorAll(".reaction-participants"),
            ).map((dialog) => dialog.getAttribute("aria-label")),
        ).toEqual(["Celebrating reaction participants"]);
        expect(container.textContent).toContain("Party participant");

        await act(async () => {
            fire.resolve(
                response({
                    next: null,
                    previous: null,
                    results: [
                        {
                            id: 1,
                            display_name: "Stale fire participant",
                            is_site_author: false,
                        },
                    ],
                }),
            );
            await fire.promise;
        });
        await flush();
        expect(
            Array.from(
                container.querySelectorAll(".reaction-participants"),
            ).map((dialog) => dialog.getAttribute("aria-label")),
        ).toEqual(["Celebrating reaction participants"]);
        expect(container.textContent).toContain("Party participant");
        expect(container.textContent).not.toContain("Stale fire participant");

        act(() => {
            root.unmount();
        });
    });

    it("ignores a stale participant error after a newer group succeeds", async () => {
        const fire = deferred<Response>();
        defaultFetch(signedIn, (url) => {
            if (url.includes("/pepeclap/participants/")) {
                return fire.promise;
            }
            if (url.includes("/pepeparty/participants/")) {
                return Promise.resolve(
                    response({
                        next: null,
                        previous: null,
                        results: [
                            {
                                id: 2,
                                display_name: "Current party participant",
                                is_site_author: false,
                            },
                        ],
                    }),
                );
            }
            return null;
        });
        const partyGroup = group({
            reaction: partyReaction,
            participants:
                "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/pepeparty/participants/",
        });
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[group(), partyGroup]}
                target={postTarget}
            />,
        );
        act(() => {
            buttonByLabel(container, "Add Clapping reaction")?.focus();
        });
        await flush();
        act(() => {
            buttonByLabel(container, "Add Celebrating reaction")?.focus();
        });
        await flush();
        await act(async () => {
            fire.reject(new Error("stale"));
            await fire.promise.catch(() => undefined);
        });

        expect(container.textContent).toContain("Current party participant");
        expect(container.textContent).not.toContain(
            "Participants could not be loaded.",
        );
        act(() => {
            root.unmount();
        });
    });

    it("invalidates an active participant request when Escape closes the surface", async () => {
        const pending = deferred<unknown>();
        let participantCalls = 0;
        const waitingResponse = {
            headers: new Headers(),
            json: () => pending.promise,
            ok: true,
            status: 200,
        } as Response;
        defaultFetch(signedIn, (url) => {
            if (!url.includes("/participants/")) {
                return null;
            }
            participantCalls += 1;
            return participantCalls === 1
                ? Promise.resolve(
                      response({
                          next: `${group().participants}?cursor=next`,
                          previous: null,
                          results: [
                              {
                                  id: 1,
                                  display_name: "Initial",
                                  is_site_author: false,
                              },
                          ],
                      }),
                  )
                : Promise.resolve(waitingResponse);
        });
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        await flush();
        const trigger = buttonByLabel(
            container,
            "View 1 participant for Clapping",
        );
        expect(trigger).toBeDefined();
        act(() => {
            trigger?.click();
        });
        await flush();
        expect(container.textContent).toContain("Initial");
        expect(
            container.querySelector(".reaction-participants"),
        ).not.toBeNull();
        act(() => {
            Array.from(container.querySelectorAll("button"))
                .find((button) => button.textContent === "Load more")
                ?.click();
        });
        await flush();
        expect(participantCalls).toBe(2);
        const escape = new KeyboardEvent("keydown", {
            key: "Escape",
            bubbles: true,
            cancelable: true,
        });
        act(() => {
            document.dispatchEvent(escape);
        });
        await flush();
        expect(escape.defaultPrevented).toBe(true);
        expect(document.activeElement).toBe(trigger);
        expect(container.querySelector(".reaction-participants")).toBeNull();

        await act(async () => {
            pending.resolve({
                next: null,
                previous: null,
                results: [
                    {
                        id: 1,
                        display_name: "Too late",
                        is_site_author: false,
                    },
                ],
            });
            await pending.promise;
        });
        await flush();
        expect(container.textContent).not.toContain("Too late");
        expect(container.querySelector(".reaction-participants")).toBeNull();
        act(() => {
            root.unmount();
        });
    });

    it("clears participant state when the reaction target changes or unmounts", async () => {
        const pending = deferred<Response>();
        defaultFetch(signedIn, (url) =>
            url.includes("/participants/") ? pending.promise : null,
        );
        const rendered = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(
                rendered.container,
                "View 1 participant for Clapping",
            )?.click();
        });
        const otherTarget: ReactionTarget = {
            kind: "comment",
            id: 77,
            slug: "другой",
            returnTo: "/posts/другой?thread=77",
        };
        act(() => {
            rendered.root.render(
                <AuthProvider>
                    <ReactionBar initialReactions={[]} target={otherTarget} />
                </AuthProvider>,
            );
        });
        await flush();
        expect(
            rendered.container.querySelector(".reaction-participants"),
        ).toBeNull();

        act(() => {
            rendered.root.unmount();
        });
        await act(async () => {
            pending.resolve(
                response({
                    next: null,
                    previous: null,
                    results: [
                        {
                            id: 1,
                            display_name: "Old target",
                            is_site_author: false,
                        },
                    ],
                }),
            );
            await pending.promise;
        });
    });

    it("deduplicates participant cursor pages by public user ID", async () => {
        let calls = 0;
        defaultFetch(signedIn, (url) => {
            if (!url.includes("/participants/")) {
                return null;
            }
            calls += 1;
            return Promise.resolve(
                calls === 1
                    ? response({
                          next: `${group().participants}?cursor=next`,
                          previous: null,
                          results: [
                              {
                                  id: 1,
                                  display_name: "One",
                                  is_site_author: false,
                              },
                          ],
                      })
                    : response({
                          next: null,
                          previous: null,
                          results: [
                              {
                                  id: 1,
                                  display_name: "One refreshed",
                                  is_site_author: false,
                              },
                              {
                                  id: 2,
                                  display_name: "Two",
                                  is_site_author: false,
                              },
                          ],
                      }),
            );
        });
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(
                container,
                "View 1 participant for Clapping",
            )?.click();
        });
        await flush();
        act(() => {
            Array.from(container.querySelectorAll("button"))
                .find((button) => button.textContent === "Load more")
                ?.click();
        });
        await flush();

        expect(
            container.querySelectorAll(".reaction-participants li"),
        ).toHaveLength(2);
        expect(container.textContent).toContain("One refreshed");
        expect(container.textContent).toContain("Two");
        act(() => {
            root.unmount();
        });
    });

    it("limits hover to fine mouse pointers and suppresses touch-triggered focus", async () => {
        let participantCalls = 0;
        let toggleCalls = 0;
        defaultFetch(signedIn, (url, options) => {
            if (url.includes("/participants/")) {
                participantCalls += 1;
                return Promise.resolve(
                    response({ next: null, previous: null, results: [] }),
                );
            }
            if (options?.method === "POST" && url.includes("/toggle/")) {
                toggleCalls += 1;
                return Promise.resolve(
                    response({
                        action: "added",
                        reactions: [group({ viewer_reacted: true })],
                    }),
                );
            }
            return null;
        });
        const { container, root } = await render(
            <ReactionBar initialReactions={[group()]} target={postTarget} />,
        );
        const pill = container.querySelector(".reaction-pill");
        const toggle = buttonByLabel(container, "Add Clapping reaction");
        const now = vi.spyOn(Date, "now").mockReturnValue(1000);

        act(() => {
            pill?.dispatchEvent(pointerEvent("pointerover", "mouse"));
        });
        expect(participantCalls).toBe(0);

        act(() => {
            toggle?.dispatchEvent(pointerEvent("pointerdown", "touch"));
            toggle?.focus();
            toggle?.click();
            toggle?.dispatchEvent(pointerEvent("pointerup", "touch"));
        });
        await flush();
        expect(toggleCalls).toBe(1);
        expect(participantCalls).toBe(0);

        vi.mocked(matchMedia).mockReturnValue({
            matches: true,
        } as MediaQueryList);
        now.mockReturnValue(3001);
        act(() => {
            pill?.dispatchEvent(pointerEvent("pointerover", "mouse"));
        });
        await flush();
        expect(participantCalls).toBe(1);
        act(() => {
            root.unmount();
        });
    });

    it("lazy-loads the picker, toggles it, searches, navigates, and restores focus", async () => {
        rememberReaction(clap.id);
        defaultFetch(signedIn);
        const { container, root } = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        const trigger = buttonByLabel(container, "Choose reaction");
        expect(trigger?.getAttribute("aria-expanded")).toBe("false");
        expect(
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([input]) => urlOf(input) === "/api/v1/reactions/catalog/",
                ),
        ).toBe(false);
        act(() => {
            trigger?.click();
        });
        await waitFor(
            () =>
                container.querySelector<HTMLInputElement>(
                    'input[placeholder="Search reactions"]',
                ) !== null,
        );
        expect(trigger?.getAttribute("aria-expanded")).toBe("true");
        act(() => {
            trigger?.click();
        });
        expect(
            container.querySelector('[aria-label="Choose a reaction"]'),
        ).toBeNull();
        expect(trigger?.getAttribute("aria-expanded")).toBe("false");
        act(() => {
            trigger?.click();
        });
        await waitFor(
            () =>
                container.querySelector('[aria-label="Choose a reaction"]') !==
                null,
        );
        act(() => {
            buttonByLabel(container, "Close reaction picker")?.click();
        });
        expect(document.activeElement).toBe(trigger);
        act(() => {
            trigger?.click();
        });
        await waitFor(
            () =>
                container.querySelector('[aria-label="Choose a reaction"]') !==
                null,
        );
        expect(buttonByLabel(container, "React with Clapping")).toBeDefined();
        const gridButtons = container.querySelectorAll<HTMLButtonElement>(
            '.reaction-picker__grid[role="group"] button',
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

        const search = container.querySelector<HTMLInputElement>(
            'input[placeholder="Search reactions"]',
        );
        act(() => {
            if (search) {
                inputValue(search, "rocket");
            }
        });
        await waitFor(
            () =>
                buttonByLabel(container, "React with Launching a rocket") !==
                undefined,
        );
        expect(
            buttonByLabel(container, "React with Launching a rocket"),
        ).toBeDefined();
        act(() => {
            container
                .querySelector('[aria-label="Choose a reaction"]')
                ?.dispatchEvent(
                    new KeyboardEvent("keydown", {
                        key: "Escape",
                        bubbles: true,
                    }),
                );
        });
        expect(
            container.querySelector('[aria-label="Choose a reaction"]'),
        ).toBeNull();
        expect(document.activeElement).toBe(trigger);
        act(() => {
            root.unmount();
        });
    });

    it("selects a custom picker item through a touch interaction", async () => {
        defaultFetch(signedIn, (url, options) => {
            if (options?.method === "POST" && url.includes("/toggle/")) {
                return Promise.resolve(
                    response({
                        action: "added",
                        reactions: [
                            group({
                                reaction: hmm,
                                viewer_reacted: true,
                                participants:
                                    "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/pepehmm/participants/",
                            }),
                        ],
                    }),
                );
            }
            return null;
        });
        const { container, root } = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        const trigger = buttonByLabel(container, "Choose reaction");
        act(() => {
            trigger?.click();
        });
        await waitFor(
            () =>
                container.querySelector('[aria-label="Choose a reaction"]') !==
                null,
        );
        const picker = container.querySelector(
            '[aria-label="Choose a reaction"]',
        );
        const option = buttonByLabel(
            picker ?? container,
            "React with Thinking",
        );
        act(() => {
            option?.dispatchEvent(pointerEvent("pointerdown", "touch"));
            option?.dispatchEvent(pointerEvent("pointerup", "touch"));
            option?.click();
        });
        await waitFor(() =>
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([, options]) =>
                        options?.method === "POST" &&
                        options.body ===
                            JSON.stringify({ reaction_id: hmm.id }),
                ),
        );
        expect(
            container.querySelector('[aria-label="Choose a reaction"]'),
        ).toBeNull();
        expect(
            buttonByLabel(container, "Remove Thinking reaction"),
        ).toBeDefined();
        expect(document.activeElement).toBe(trigger);

        act(() => {
            root.unmount();
        });
    });

    it("restores a catalog-ID pending intent after OAuth but waits for confirmation", async () => {
        defaultFetch(anonymous);
        const anonymousRender = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        act(() => {
            buttonByLabel(
                anonymousRender.container,
                "Choose reaction",
            )?.click();
        });
        await waitFor(
            () =>
                buttonByLabel(
                    anonymousRender.container,
                    "React with Clapping",
                ) !== undefined,
        );
        act(() => {
            buttonByLabel(
                anonymousRender.container,
                "React with Clapping",
            )?.click();
        });
        const login =
            anonymousRender.container.querySelector<HTMLAnchorElement>(
                'a[href^="/login?next="]',
            );
        expect(login?.href).toContain(
            "next=%2Fposts%2F%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80",
        );
        expect(loadPendingReaction(postTarget)).toBe(clap.id);
        act(() => {
            anonymousRender.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        resetReactionCatalogForTests();
        let postCalls = 0;
        defaultFetch(signedIn, (url, options) => {
            if (options?.method === "POST" && url.includes("/toggle/")) {
                postCalls += 1;
                return Promise.resolve(
                    response({
                        action: "added",
                        reactions: [
                            group({
                                viewer_reacted: true,
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
        expect(
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([input]) => urlOf(input) === "/api/v1/reactions/config/",
                ),
        ).toBe(false);
        expect(
            vi
                .mocked(fetch)
                .mock.calls.some(
                    ([input]) => urlOf(input) === "/api/v1/reactions/catalog/",
                ),
        ).toBe(true);
        expect(authenticatedRender.container.textContent).toContain(
            "Add your saved Pepe clap reaction?",
        );
        act(() => {
            Array.from(authenticatedRender.container.querySelectorAll("button"))
                .find((button) => button.textContent === "Confirm")
                ?.click();
        });
        await flush();
        expect(postCalls).toBe(1);
        expect(loadPendingReaction(postTarget)).toBeNull();
        expect(loadPendingReaction(postTarget, Date.now(), 42)).toBeNull();
        act(() => {
            authenticatedRender.root.unmount();
        });
    });

    it("discards the latest target intent without reviving an older catalog ID", async () => {
        const now = Date.now();
        savePendingReaction(postTarget, clap.id, now - 1);
        savePendingReaction(postTarget, hmm.id, now);
        defaultFetch(signedIn);
        const first = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        expect(first.container.textContent).toContain(
            "Add your saved Pepe hmm reaction?",
        );
        act(() => {
            Array.from(first.container.querySelectorAll("button"))
                .find((button) => button.textContent === "Discard")
                ?.click();
        });
        expect(loadPendingReaction(postTarget, now + 1)).toBeNull();
        expect(loadPendingReaction(postTarget, now + 1, 42)).toBeNull();
        act(() => {
            first.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        resetReactionCatalogForTests();
        defaultFetch(signedIn);
        const reloaded = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        expect(reloaded.container.textContent).not.toContain("saved");
        expect(loadPendingReaction(postTarget, now + 2)).toBeNull();
        act(() => {
            reloaded.root.unmount();
        });
    });
});
