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
    isValidStoredEmoji,
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
    resetReactionConfigForTests();
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

    it("strictly validates recent and pending emoji without the picker dataset", async () => {
        for (let index = 0; index < 20; index += 1) {
            rememberReaction(index % 2 ? "🔥" : `🎉`);
        }
        expect(loadRecentReactions()).toEqual(["🔥", "🎉"]);

        localStorage.setItem(
            "kw:reaction-recent:v1",
            JSON.stringify([
                "🔥",
                "hello",
                ":custom:",
                7,
                "🔥\u202e",
                "👩‍",
                "🔥‍",
                "🔥️",
                "☕️",
                "🇺",
                "🇺🇸🇨",
                "🏳️‍",
            ]),
        );
        expect(loadRecentReactions()).toEqual(["🔥"]);

        for (const malformed of ["👩‍", "🔥‍", "🔥️", "☕️", "🇺", "🇺🇸🇨", "🏳️‍"]) {
            expect(isValidStoredEmoji(malformed)).toBe(false);
            savePendingReaction(postTarget, malformed, 90);
            expect(loadPendingReaction(postTarget, 91)).toBeNull();
        }

        const pendingKey =
            "kw:reaction-intent:v1:%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80:post:9:%F0%9F%94%A5";
        for (const malformedJson of [
            "null",
            "[]",
            "{}",
            '{"emoji":"👩‍","createdAt":90}',
            '{"emoji":"🔥","createdAt":"90"}',
        ]) {
            sessionStorage.setItem(pendingKey, malformedJson);
            expect(loadPendingReaction(postTarget, 91)).toBeNull();
            expect(sessionStorage.getItem(pendingKey)).toBeNull();
        }

        const data = (await import("@emoji-mart/data")).default as {
            emojis: Record<string, { skins: Array<{ native: string }> }>;
        };
        for (const item of Object.values(data.emojis)) {
            for (const skin of item.skins) {
                expect(isValidStoredEmoji(skin.native)).toBe(true);
            }
        }
    });

    it("keeps one newest pending intent per target and clears the whole target", () => {
        const otherTarget: ReactionTarget = {
            ...postTarget,
            id: 10,
        };
        savePendingReaction(otherTarget, "❤️", 50);
        savePendingReaction(postTarget, "🔥", 100);
        savePendingReaction(postTarget, "🎉", 200);

        expect(loadPendingReaction(postTarget, 201)).toBe("🎉");
        expect(loadPendingReaction(otherTarget, 201)).toBe("❤️");
        expect(
            Array.from({ length: sessionStorage.length }, (_, index) =>
                sessionStorage.key(index),
            ).filter((key) => key?.includes(":post:9:")),
        ).toHaveLength(1);

        clearPendingReaction(postTarget);
        expect(loadPendingReaction(postTarget, 202)).toBeNull();
        expect(loadPendingReaction(otherTarget, 202)).toBe("❤️");
    });

    it("chooses legacy duplicate intents by createdAt and preserves TTL", () => {
        const prefix =
            "kw:reaction-intent:v1:%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80:post:9:";
        sessionStorage.setItem(
            `${prefix}${encodeURIComponent("🎉")}`,
            JSON.stringify({ emoji: "🎉", createdAt: 200 }),
        );
        sessionStorage.setItem(
            `${prefix}${encodeURIComponent("🔥")}`,
            JSON.stringify({ emoji: "🔥", createdAt: 100 }),
        );

        expect(loadPendingReaction(postTarget, 201)).toBe("🎉");
        expect(sessionStorage.length).toBe(1);
        expect(
            loadPendingReaction(
                postTarget,
                200 + reactionStorageLimits.intentTtlMs + 1,
            ),
        ).toBeNull();
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
            buttonByLabel(container, "Add 🔥 reaction")?.click();
        });
        await flush();
        expect(buttonByLabel(container, "Add 🔥 reaction")).toBeDefined();
        expect(container.textContent).toContain("previous state was restored");
        expect(sources.slice(0, 2)).toEqual(["optimistic", "rollback"]);

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
        const countTrigger = buttonByLabel(
            container,
            "View 1 participant for 🔥",
        );
        act(() => {
            countTrigger?.click();
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
            document.dispatchEvent(
                new KeyboardEvent("keydown", {
                    key: "Escape",
                    bubbles: true,
                }),
            );
        });
        expect(
            container.querySelector('[aria-label="🔥 reaction participants"]'),
        ).toBeNull();
        expect(document.activeElement).toBe(countTrigger);
        act(() => {
            root.unmount();
        });
    });

    it("ignores stale participant success and error responses after switching emoji", async () => {
        const fire = deferred<Response>();
        const party = deferred<Response>();
        defaultFetch(signedIn, (url) => {
            if (url.includes("%F0%9F%94%A5/participants/")) {
                return fire.promise;
            }
            if (url.includes("%F0%9F%8E%89/participants/")) {
                return party.promise;
            }
            return null;
        });
        const partyGroup = group({
            emoji: "🎉",
            participants:
                "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/%F0%9F%8E%89/participants/",
        });
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[group(), partyGroup]}
                target={postTarget}
            />,
        );

        act(() => {
            buttonByLabel(container, "Add 🔥 reaction")?.focus();
        });
        await flush();
        act(() => {
            buttonByLabel(container, "Add 🎉 reaction")?.focus();
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
        ).toEqual(["🎉 reaction participants"]);
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
        ).toEqual(["🎉 reaction participants"]);
        expect(container.textContent).toContain("Party participant");
        expect(container.textContent).not.toContain("Stale fire participant");

        act(() => {
            root.unmount();
        });
    });

    it("ignores a stale participant error after a newer group succeeds", async () => {
        const fire = deferred<Response>();
        defaultFetch(signedIn, (url) => {
            if (url.includes("%F0%9F%94%A5/participants/")) {
                return fire.promise;
            }
            if (url.includes("%F0%9F%8E%89/participants/")) {
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
            emoji: "🎉",
            participants:
                "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/reactions/%F0%9F%8E%89/participants/",
        });
        const { container, root } = await render(
            <ReactionBar
                initialReactions={[group(), partyGroup]}
                target={postTarget}
            />,
        );
        act(() => {
            buttonByLabel(container, "Add 🔥 reaction")?.focus();
        });
        await flush();
        act(() => {
            buttonByLabel(container, "Add 🎉 reaction")?.focus();
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
        const trigger = buttonByLabel(container, "View 1 participant for 🔥");
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
                "View 1 participant for 🔥",
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
            buttonByLabel(container, "View 1 participant for 🔥")?.click();
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
        const toggle = buttonByLabel(container, "Add 🔥 reaction");
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

    it("discards the entire latest target intent without reviving an older emoji", async () => {
        const now = Date.now();
        savePendingReaction(postTarget, "🔥", now - 1);
        savePendingReaction(postTarget, "🎉", now);
        defaultFetch(signedIn);
        const first = await render(
            <ReactionBar initialReactions={[]} target={postTarget} />,
        );
        expect(first.container.textContent).toContain(
            "Add your saved 🎉 reaction?",
        );
        act(() => {
            Array.from(first.container.querySelectorAll("button"))
                .find((button) => button.textContent === "Discard")
                ?.click();
        });
        expect(loadPendingReaction(postTarget, now + 1)).toBeNull();
        act(() => {
            first.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        resetReactionConfigForTests();
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
