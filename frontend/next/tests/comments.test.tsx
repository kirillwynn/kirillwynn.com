// @vitest-environment jsdom

import { readFileSync } from "node:fs";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/auth-provider";
import { CommentsSection } from "@/components/comments-section";
import type { MeResponse } from "@/lib/auth";
import {
    COMMENT_DRAFT_MAX_LENGTH,
    COMMENT_DRAFT_TTL_MS,
    clearCommentDraft,
    loadCommentDraft,
    saveCommentDraft,
} from "@/lib/comment-drafts";
import {
    applyCommentReactionChange,
    reconcileComment,
    reconcileReplies,
    reconcileRoots,
} from "@/lib/comment-reconciliation";
import { codePointLength, truncateCodePoints } from "@/lib/comment-text";
import {
    createComment,
    createThreadReply,
    deletePublicComment,
    editPublicComment,
    getComments,
    type CommentPage,
    type PublicComment,
    type ThreadPage,
} from "@/lib/comments";
import { resetReactionMutationCoordinatorForTests } from "@/lib/reaction-mutation-coordinator";
import {
    resetReactionConfigForTests,
    type ReactionDescriptor,
    type ReactionGroup,
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

const authenticated: MeResponse = {
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

function comment(overrides: Partial<PublicComment> = {}): PublicComment {
    return {
        id: 7,
        kind: "comment",
        body: "<script>plain text</script>",
        status: "visible",
        author: {
            id: 3,
            display_name: "<Safe author>",
            is_site_author: false,
        },
        thread_root_id: null,
        reply_to: null,
        created_at: "2026-07-26T20:00:00Z",
        updated_at: "2026-07-26T20:00:00Z",
        edited_at: null,
        reply_count: 1,
        last_reply_at: "2026-07-26T20:05:00Z",
        reactions: [],
        viewer: {
            can_edit: false,
            can_delete: false,
            can_reply: false,
            can_react: false,
        },
        ...overrides,
    };
}

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
    ...clap,
    id: "pepehmm",
    name: "Pepe hmm",
    label: "Thinking",
    kind: "static",
    asset_url: "/media/reactions/pepehmm/hash/asset.webp",
    poster_url: "/media/reactions/pepehmm/hash/asset.webp",
    version: "sha256-hmm",
};

const love: ReactionDescriptor = {
    ...hmm,
    id: "pepelove",
    name: "Pepe love",
    label: "Sending love",
    asset_url: "/media/reactions/pepelove/hash/asset.webp",
    poster_url: "/media/reactions/pepelove/hash/asset.webp",
    version: "sha256-love",
};

function reaction(count: number, viewerReacted = false): ReactionGroup {
    return {
        reaction: clap,
        count,
        viewer_reacted: viewerReacted,
        participants: "/api/v1/comments/7/reactions/pepeclap/participants/",
    };
}

function page(results: PublicComment[]): CommentPage {
    return { next: null, previous: null, results };
}

function response(
    payload: unknown,
    status = 200,
    extraHeaders?: HeadersInit,
): Response {
    const headers = new Headers(extraHeaders);
    headers.set("Content-Type", "application/json");
    return new Response(status === 204 ? null : JSON.stringify(payload), {
        status,
        headers,
    });
}

async function flush(): Promise<void> {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
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

function typeInTextarea(
    textarea: HTMLTextAreaElement | null,
    value: string,
): void {
    if (!textarea) {
        return;
    }
    // React tracks the instance value; invoke the native setter to simulate typing.
    // eslint-disable-next-line @typescript-eslint/unbound-method
    const setter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
    )?.set;
    setter?.call(textarea, value);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

function clickWithoutNavigation(link: HTMLAnchorElement | null): void {
    link?.addEventListener(
        "click",
        (event) => {
            event.preventDefault();
        },
        { once: true },
    );
    act(() => {
        link?.click();
    });
}

function buttonByLabel(
    container: ParentNode,
    label: string,
): HTMLButtonElement | undefined {
    return Array.from(
        container.querySelectorAll<HTMLButtonElement>("button"),
    ).find((button) => button.getAttribute("aria-label") === label);
}

function mainCommentCard(
    container: ParentNode,
    commentId: number,
): HTMLElement | undefined {
    return Array.from(
        container.querySelectorAll<HTMLElement>(
            `[data-comment-id="${String(commentId)}"]`,
        ),
    ).find((card) => card.closest('[role="dialog"]') === null);
}

async function renderComments(
    me: MeResponse,
    roots: PublicComment[],
    thread?: ThreadPage,
    extra?: (url: string, options?: RequestInit) => Promise<Response> | null,
): Promise<{ container: HTMLDivElement; root: Root }> {
    vi.mocked(fetch).mockImplementation((input, options) => {
        const url =
            typeof input === "string"
                ? input
                : input instanceof URL
                  ? input.href
                  : input.url;
        const handled = extra?.(url, options);
        if (handled) {
            return handled;
        }
        if (url === "/api/me/") {
            return Promise.resolve(response(me));
        }
        if (url === "/api/v1/reactions/config/") {
            return Promise.resolve(
                response({ quick_reactions: [clap, hmm, love] }),
            );
        }
        if (url.includes("/thread/") && thread) {
            return Promise.resolve(response(thread));
        }
        if (url.includes("/comments/")) {
            return Promise.resolve(response(page(roots)));
        }
        return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    act(() => {
        root.render(
            <AuthProvider>
                <CommentsSection slug="привет-мир" />
            </AuthProvider>,
        );
    });
    await flush();
    return { container, root };
}

beforeEach(() => {
    resetReactionConfigForTests();
    resetReactionMutationCoordinatorForTests();
    vi.stubGlobal("fetch", vi.fn());
    window.sessionStorage.clear();
    window.history.replaceState(
        {},
        "",
        "/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82",
    );
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

describe("comment API client", () => {
    it("encodes a Unicode slug once and always bypasses public caches", async () => {
        vi.mocked(fetch).mockResolvedValueOnce(response(page([])));

        await getComments("привет-мир");

        expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
            "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80/comments/",
        );
        const options = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
        expect(options.cache).toBe("no-store");
        expect(options.credentials).toBe("same-origin");
    });

    it("sends CSRF on create, reply, edit, and delete", async () => {
        vi.mocked(fetch)
            .mockResolvedValueOnce(response(comment(), 201))
            .mockResolvedValueOnce(response(comment({ kind: "reply" }), 201))
            .mockResolvedValueOnce(response(comment({ body: "Edited" })))
            .mockResolvedValueOnce(response(null, 204));

        await createComment("привет", "Body", "csrf");
        await createThreadReply(7, "Reply", "csrf");
        await editPublicComment(7, "Edited", "csrf");
        await deletePublicComment(7, "csrf");

        for (const call of vi.mocked(fetch).mock.calls) {
            const headers = call[1]?.headers as Headers;
            expect(headers.get("X-CSRFToken")).toBe("csrf");
        }
        expect(
            vi.mocked(fetch).mock.calls.map((call) => call[1]?.method),
        ).toEqual(["POST", "POST", "PATCH", "DELETE"]);
    });

    it("surfaces 429 Retry-After without losing the server message", async () => {
        vi.mocked(fetch).mockResolvedValueOnce(
            response({ detail: "Too many comment mutations." }, 429, {
                "Retry-After": "17",
            }),
        );

        await expect(
            createComment("post", "Body", "csrf"),
        ).rejects.toMatchObject({
            status: 429,
            retryAfter: 17,
            message: "Too many comment mutations.",
        });
    });

    it("rejects external or cross-endpoint cursor URLs before fetch", () => {
        expect(() =>
            getComments("привет", "https://evil.example/comments/?cursor=x"),
        ).toThrow("The comments cursor is invalid.");
        expect(() =>
            getComments(
                "привет",
                "/api/v1/comments/7/thread/?cursor=cross-endpoint",
            ),
        ).toThrow("The comments cursor is invalid.");
        expect(fetch).not.toHaveBeenCalled();
    });
});

describe("pending OAuth drafts", () => {
    it("namespaces Unicode posts, thread IDs, and users", () => {
        saveCommentDraft({
            slug: "привет",
            kind: "comment",
            userId: 1,
            body: "Post one",
            now: 100,
        });
        saveCommentDraft({
            slug: "другой",
            kind: "comment",
            userId: 1,
            body: "Post two",
            now: 100,
        });
        saveCommentDraft({
            slug: "привет",
            kind: "reply",
            threadId: 9,
            userId: 2,
            body: "Thread",
            now: 100,
        });

        expect(
            loadCommentDraft({
                slug: "привет",
                kind: "comment",
                userId: 1,
                now: 101,
            }),
        ).toBe("Post one");
        expect(
            loadCommentDraft({
                slug: "привет",
                kind: "reply",
                threadId: 10,
                userId: 2,
                now: 101,
            }),
        ).toBe("");
    });

    it("migrates pending-auth text, applies TTL/size, and supports discard", () => {
        saveCommentDraft({
            slug: "привет",
            kind: "comment",
            userId: null,
            body: "x".repeat(COMMENT_DRAFT_MAX_LENGTH + 10),
            now: 100,
        });
        const restored = loadCommentDraft({
            slug: "привет",
            kind: "comment",
            userId: 42,
            now: 101,
        });
        expect(restored).toHaveLength(COMMENT_DRAFT_MAX_LENGTH);

        clearCommentDraft({
            slug: "привет",
            kind: "comment",
            userId: 42,
        });
        expect(
            loadCommentDraft({
                slug: "привет",
                kind: "comment",
                userId: 42,
                now: 102,
            }),
        ).toBe("");

        saveCommentDraft({
            slug: "привет",
            kind: "comment",
            userId: 42,
            body: "Expired",
            now: 100,
        });
        expect(
            loadCommentDraft({
                slug: "привет",
                kind: "comment",
                userId: 42,
                now: 100 + COMMENT_DRAFT_TTL_MS + 1,
            }),
        ).toBe("");
    });

    it("counts and truncates Unicode code points without splitting astral characters", () => {
        const emoji = "🧑";
        const exactEmojiBoundary = emoji.repeat(COMMENT_DRAFT_MAX_LENGTH);
        const truncatedEmoji = truncateCodePoints(
            `${exactEmojiBoundary}${emoji}`,
        );

        expect(codePointLength("a".repeat(COMMENT_DRAFT_MAX_LENGTH))).toBe(
            COMMENT_DRAFT_MAX_LENGTH,
        );
        expect(codePointLength(truncatedEmoji)).toBe(COMMENT_DRAFT_MAX_LENGTH);
        expect(truncatedEmoji).toBe(exactEmojiBoundary);
        expect(truncateCodePoints("A🧑B", 2)).toBe("A🧑");
        expect(truncateCodePoints("A🧑B", 2)).not.toMatch(/[\uD800-\uDBFF]$/);
    });

    it("truncates pasted and stored drafts by code point", () => {
        const oversized = `${"🧑".repeat(COMMENT_DRAFT_MAX_LENGTH)}tail`;
        saveCommentDraft({
            slug: "эмодзи",
            kind: "reply",
            threadId: 11,
            userId: null,
            body: oversized,
            now: 100,
        });

        const restored = loadCommentDraft({
            slug: "эмодзи",
            kind: "reply",
            threadId: 11,
            userId: null,
            now: 101,
        });
        expect(codePointLength(restored)).toBe(COMMENT_DRAFT_MAX_LENGTH);
        expect(restored).toBe("🧑".repeat(COMMENT_DRAFT_MAX_LENGTH));
    });
});

describe("comment reconciliation", () => {
    it("deduplicates cursor pages, refreshes objects, and preserves thread chronology", () => {
        const initial = Array.from({ length: 20 }, (_, index) =>
            comment({
                id: index + 1,
                kind: "reply",
                thread_root_id: 7,
                body: `Reply ${String(index + 1)}`,
                created_at: `2026-07-26T20:${String(index).padStart(2, "0")}:00Z`,
            }),
        );
        const created = comment({
            id: 30,
            kind: "reply",
            thread_root_id: 7,
            body: "Locally created",
            created_at: "2026-07-26T20:30:00Z",
        });
        const nextPage = [
            ...Array.from({ length: 5 }, (_, index) =>
                comment({
                    id: index + 21,
                    kind: "reply",
                    thread_root_id: 7,
                    body: `Reply ${String(index + 21)}`,
                    created_at: `2026-07-26T20:${String(index + 20).padStart(2, "0")}:00Z`,
                }),
            ),
            { ...created, body: "Fresh server copy" },
        ];

        const optimistic = reconcileReplies(initial, [created]);
        const merged = reconcileReplies(optimistic, nextPage);
        const repeated = reconcileReplies(merged, nextPage);

        expect(repeated.map((reply) => reply.id)).toEqual([
            ...Array.from({ length: 25 }, (_, index) => index + 1),
            30,
        ]);
        expect(new Set(repeated.map((reply) => reply.id)).size).toBe(
            repeated.length,
        );
        expect(repeated.at(-1)?.body).toBe("Fresh server copy");
        expect(repeated).toEqual(merged);
    });

    it("keeps roots newest-first with a stable descending ID tie-breaker", () => {
        const sameTime = "2026-07-26T20:00:00Z";
        const merged = reconcileRoots(
            [comment({ id: 1, created_at: sameTime })],
            [
                comment({ id: 2, created_at: sameTime }),
                comment({
                    id: 3,
                    created_at: "2026-07-26T21:00:00Z",
                }),
                comment({
                    id: 1,
                    created_at: sameTime,
                    body: "Fresh root",
                }),
            ],
        );
        expect(merged.map((root) => root.id)).toEqual([3, 2, 1]);
        expect(merged.at(-1)?.body).toBe("Fresh root");
    });

    it("preserves optimistic reactions across stale cursor, thread, and edit responses", () => {
        const optimistic = applyCommentReactionChange(
            comment({ reactions: [reaction(1)] }),
            {
                reactions: [reaction(2, true)],
                revision: 7,
                source: "optimistic",
            },
        );
        const staleCursorCopy = comment({
            body: "Fresh edited body",
            reactions: [reaction(1)],
        });

        const [merged] = reconcileRoots([optimistic], [staleCursorCopy]);
        const threadMerged = reconcileComment(merged, {
            ...staleCursorCopy,
            body: "Fresh thread body",
        });

        expect(merged.body).toBe("Fresh edited body");
        expect(merged.reactions).toEqual([reaction(2, true)]);
        expect(merged.reaction_pending_revision).toBe(7);
        expect(threadMerged.body).toBe("Fresh thread body");
        expect(threadMerged.reactions).toEqual([reaction(2, true)]);
        expect(threadMerged.reaction_pending_revision).toBe(7);
    });

    it("settles authoritative and rollback states and accepts later server aggregates", () => {
        const initial = comment({ reactions: [reaction(1)] });
        const optimistic = applyCommentReactionChange(initial, {
            reactions: [reaction(2, true)],
            revision: 8,
            source: "optimistic",
        });
        const authoritative = applyCommentReactionChange(optimistic, {
            reactions: [reaction(3, true)],
            revision: 8,
            source: "authoritative",
        });
        const fresh = reconcileComment(authoritative, {
            ...initial,
            reactions: [reaction(5, true)],
        });

        expect(authoritative.reaction_pending_revision).toBeUndefined();
        expect(authoritative.reactions).toEqual([reaction(3, true)]);
        expect(fresh.reactions).toEqual([reaction(5, true)]);

        const rolledBack = applyCommentReactionChange(optimistic, {
            reactions: initial.reactions,
            revision: 8,
            source: "rollback",
        });
        expect(rolledBack.reaction_pending_revision).toBeUndefined();
        expect(rolledBack.reactions).toEqual(initial.reactions);
    });

    it("ignores an older mutation response and lets tombstones win", () => {
        const first = applyCommentReactionChange(comment(), {
            reactions: [reaction(1, true)],
            revision: 10,
            source: "optimistic",
        });
        const second = applyCommentReactionChange(first, {
            reactions: [reaction(2, true)],
            revision: 11,
            source: "optimistic",
        });
        const staleSuccess = applyCommentReactionChange(second, {
            reactions: [reaction(9, true)],
            revision: 10,
            source: "authoritative",
        });
        const tombstone = reconcileComment(staleSuccess, {
            ...comment(),
            body: null,
            status: "deleted",
            reactions: [reaction(99, true)],
        });

        expect(staleSuccess.reactions).toEqual([reaction(2, true)]);
        expect(staleSuccess.reaction_pending_revision).toBe(11);
        expect(tombstone.reactions).toEqual([]);
        expect(tombstone.reaction_pending_revision).toBeUndefined();
    });
});

describe("comments and Slack-style thread UI", () => {
    it("shows anonymous comments as escaped text with login and tombstones", async () => {
        const { container, root } = await renderComments(anonymous, [
            comment(),
            comment({
                id: 8,
                body: null,
                status: "deleted",
                reply_count: 0,
            }),
            comment({
                id: 9,
                body: null,
                status: "hidden",
                reply_count: 0,
            }),
        ]);

        expect(container.textContent).toContain("<script>plain text</script>");
        expect(container.innerHTML).toContain("&lt;script&gt;plain text");
        expect(container.textContent).toContain("[deleted]");
        expect(container.textContent).toContain("[hidden]");
        expect(container.textContent).toContain("Login to comment");
        expect(container.querySelector("#new-comment")).not.toBeNull();
        act(() => {
            root.unmount();
        });
    });

    it("preserves an anonymous Unicode-post draft through OAuth without auto-submit", async () => {
        const anonymousRender = await renderComments(anonymous, []);
        const pendingBody = "Черновик 🧑 для входа";
        act(() => {
            typeInTextarea(
                anonymousRender.container.querySelector("#new-comment"),
                pendingBody,
            );
        });

        const login = Array.from(
            anonymousRender.container.querySelectorAll<HTMLAnchorElement>("a"),
        ).find((link) => link.textContent === "Login to comment");
        expect(login?.href).toContain(
            "next=%2Fposts%2F%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80",
        );
        expect(
            loadCommentDraft({
                slug: "привет-мир",
                kind: "comment",
                userId: null,
            }),
        ).toBe(pendingBody);
        clickWithoutNavigation(login ?? null);
        act(() => {
            anonymousRender.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        const authenticatedRender = await renderComments(authenticated, []);
        const restored =
            authenticatedRender.container.querySelector<HTMLTextAreaElement>(
                "#new-comment",
            );
        expect(restored?.value).toBe(pendingBody);
        expect(
            vi
                .mocked(fetch)
                .mock.calls.filter((call) => call[1]?.method === "POST"),
        ).toHaveLength(0);

        const discard = Array.from(
            authenticatedRender.container.querySelectorAll("button"),
        ).find((button) => button.textContent === "Discard");
        act(() => {
            discard?.click();
        });
        expect(
            loadCommentDraft({
                slug: "привет-мир",
                kind: "comment",
                userId: 42,
            }),
        ).toBe("");

        act(() => {
            typeInTextarea(restored, "Publish after review");
        });
        vi.mocked(fetch).mockResolvedValueOnce(
            response(
                comment({
                    id: 99,
                    body: "Publish after review",
                    reply_count: 0,
                }),
                201,
            ),
        );
        const submit = Array.from(
            authenticatedRender.container.querySelectorAll("button"),
        ).find((button) => button.textContent === "Comment");
        act(() => {
            submit?.click();
        });
        await flush();
        expect(
            loadCommentDraft({
                slug: "привет-мир",
                kind: "comment",
                userId: 42,
            }),
        ).toBe("");
        act(() => {
            authenticatedRender.root.unmount();
        });
    });

    it("shows authenticated and banned composer states", async () => {
        const authenticatedRender = await renderComments(authenticated, []);
        expect(
            authenticatedRender.container.querySelector("#new-comment"),
        ).not.toBeNull();
        act(() => {
            authenticatedRender.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        const banned = structuredClone(authenticated);
        if (banned.user) {
            banned.user.is_banned = true;
            banned.user.can_interact = false;
        }
        const bannedRender = await renderComments(banned, []);
        expect(bannedRender.container.textContent).toContain("read-only");
        expect(bannedRender.container.querySelector("#new-comment")).toBeNull();
        act(() => {
            bannedRender.root.unmount();
        });
    });

    it("creates a comment from the authenticated composer", async () => {
        const { container, root } = await renderComments(authenticated, []);
        const created = comment({
            id: 99,
            body: "Created in UI",
            reply_count: 0,
            viewer: {
                can_edit: true,
                can_delete: true,
                can_reply: true,
                can_react: true,
            },
        });
        vi.mocked(fetch).mockResolvedValueOnce(response(created, 201));
        const textarea =
            container.querySelector<HTMLTextAreaElement>("#new-comment");
        act(() => {
            typeInTextarea(textarea, "Created in UI");
        });
        const submit = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Comment",
        );
        act(() => {
            submit?.click();
        });
        await flush();

        expect(container.textContent).toContain("Created in UI");
        const mutation = vi
            .mocked(fetch)
            .mock.calls.find((call) => call[1]?.method === "POST");
        expect((mutation?.[1]?.headers as Headers).get("X-CSRFToken")).toBe(
            "masked-csrf",
        );
        act(() => {
            root.unmount();
        });
    });

    it("uses code-point limits for pasted root, reply, and edit text", async () => {
        const editableRoot = comment({
            viewer: {
                can_edit: true,
                can_delete: true,
                can_reply: true,
                can_react: true,
            },
        });
        const { container, root } = await renderComments(
            authenticated,
            [editableRoot],
            { ...page([]), root: editableRoot },
        );
        const oversized = `${"🧑".repeat(COMMENT_DRAFT_MAX_LENGTH)}x`;
        const rootComposer =
            container.querySelector<HTMLTextAreaElement>("#new-comment");
        act(() => {
            typeInTextarea(rootComposer, oversized);
        });
        expect(codePointLength(rootComposer?.value ?? "")).toBe(
            COMMENT_DRAFT_MAX_LENGTH,
        );
        expect(rootComposer?.hasAttribute("maxlength")).toBe(false);

        const editButton = Array.from(
            container.querySelectorAll("button"),
        ).find((button) => button.textContent === "Edit");
        act(() => {
            editButton?.click();
        });
        const editTextarea =
            container.querySelector<HTMLTextAreaElement>("#edit-comment-7");
        act(() => {
            typeInTextarea(editTextarea, `A${oversized}`);
        });
        expect(codePointLength(editTextarea?.value ?? "")).toBe(
            COMMENT_DRAFT_MAX_LENGTH,
        );
        expect(editTextarea?.value.endsWith("\uD83E")).toBe(false);
        vi.mocked(fetch).mockResolvedValueOnce(
            response({
                ...editableRoot,
                body: editTextarea?.value ?? "",
            }),
        );
        const saveEdit = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Save",
        );
        act(() => {
            saveEdit?.click();
        });
        await flush();
        const patch = vi
            .mocked(fetch)
            .mock.calls.find((call) => call[1]?.method === "PATCH");
        const requestBody = patch?.[1]?.body;
        expect(typeof requestBody).toBe("string");
        if (typeof requestBody !== "string") {
            throw new TypeError("Expected a JSON string request body.");
        }
        const patchBody = JSON.parse(requestBody) as {
            body: string;
        };
        expect(codePointLength(patchBody.body)).toBe(COMMENT_DRAFT_MAX_LENGTH);

        const replyTrigger = Array.from(
            container.querySelectorAll("button"),
        ).find((button) => button.textContent === "Reply");
        act(() => {
            replyTrigger?.click();
        });
        await flush();
        const replyTextarea =
            container.querySelector<HTMLTextAreaElement>("#thread-reply-7");
        act(() => {
            typeInTextarea(replyTextarea, oversized);
        });
        expect(codePointLength(replyTextarea?.value ?? "")).toBe(
            COMMENT_DRAFT_MAX_LENGTH,
        );
        expect(replyTextarea?.hasAttribute("maxlength")).toBe(false);
        expect(
            codePointLength(
                loadCommentDraft({
                    slug: "привет-мир",
                    kind: "reply",
                    threadId: 7,
                    userId: 42,
                }),
            ),
        ).toBe(COMMENT_DRAFT_MAX_LENGTH);
        act(() => {
            root.unmount();
        });
    });

    it("renders server validation and Retry-After errors in the live region", async () => {
        const { container, root } = await renderComments(authenticated, []);
        vi.mocked(fetch).mockResolvedValueOnce(
            response({ detail: "Too many comment mutations." }, 429, {
                "Retry-After": "12",
            }),
        );
        const textarea =
            container.querySelector<HTMLTextAreaElement>("#new-comment");
        act(() => {
            typeInTextarea(textarea, "Rate limited");
        });
        const submit = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Comment",
        );
        act(() => {
            submit?.click();
        });
        await flush();

        expect(
            container.querySelector('[role="alert"]')?.textContent,
        ).toContain("Retry in about 12 seconds");
        act(() => {
            root.unmount();
        });
    });

    it("preserves text and returns to login when the session expires", async () => {
        const { container, root } = await renderComments(authenticated, []);
        vi.mocked(fetch)
            .mockResolvedValueOnce(response({ detail: "Expired." }, 403))
            .mockResolvedValueOnce(response(anonymous));
        const textarea =
            container.querySelector<HTMLTextAreaElement>("#new-comment");
        act(() => {
            typeInTextarea(textarea, "Keep after OAuth");
        });
        const submit = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Comment",
        );
        act(() => {
            submit?.click();
        });
        await flush();
        await flush();

        expect(container.textContent).toContain("Login to comment");
        expect(
            loadCommentDraft({
                slug: "привет-мир",
                kind: "comment",
                userId: 100,
            }),
        ).toBe("Keep after OAuth");
        act(() => {
            root.unmount();
        });
    });

    it("preserves an anonymous thread draft across OAuth and reopens the Unicode route", async () => {
        const rootComment = comment({ reply_count: 1 });
        const thread = {
            ...page([
                comment({
                    id: 10,
                    kind: "reply" as const,
                    thread_root_id: 7,
                    body: "Existing reply",
                    reply_count: 0,
                }),
            ]),
            root: rootComment,
        };
        const anonymousRender = await renderComments(
            anonymous,
            [rootComment],
            thread,
        );
        const open = Array.from(
            anonymousRender.container.querySelectorAll("button"),
        ).find((button) => button.textContent === "Reply");
        act(() => {
            open?.click();
        });
        await flush();

        const pendingBody = "Ответ 🧵 после OAuth";
        const pendingTextarea =
            anonymousRender.container.querySelector<HTMLTextAreaElement>(
                "#thread-reply-7",
            );
        expect(pendingTextarea).not.toBeNull();
        act(() => {
            typeInTextarea(pendingTextarea, pendingBody);
        });
        const login = Array.from(
            anonymousRender.container.querySelectorAll<HTMLAnchorElement>("a"),
        ).find((link) => link.textContent === "Login to reply");
        expect(login?.href).toContain(
            "next=%2Fposts%2F%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80%3Fthread%3D7",
        );
        clickWithoutNavigation(login ?? null);
        expect(
            loadCommentDraft({
                slug: "привет-мир",
                kind: "reply",
                threadId: 7,
                userId: null,
            }),
        ).toBe(pendingBody);
        act(() => {
            anonymousRender.root.unmount();
        });

        document.body.replaceChildren();
        vi.mocked(fetch).mockReset();
        const authenticatedRoot = comment({
            reply_count: 1,
            viewer: {
                can_edit: false,
                can_delete: false,
                can_reply: true,
                can_react: true,
            },
        });
        const authenticatedRender = await renderComments(
            authenticated,
            [authenticatedRoot],
            { ...thread, root: authenticatedRoot },
        );
        await flush();
        const restored =
            authenticatedRender.container.querySelector<HTMLTextAreaElement>(
                "#thread-reply-7",
            );
        expect(window.location.search).toBe("?thread=7");
        expect(restored?.value).toBe(pendingBody);
        expect(
            vi
                .mocked(fetch)
                .mock.calls.filter((call) => call[1]?.method === "POST"),
        ).toHaveLength(0);

        vi.mocked(fetch).mockResolvedValueOnce(
            response(
                comment({
                    id: 11,
                    kind: "reply",
                    thread_root_id: 7,
                    body: pendingBody,
                    reply_count: 0,
                    created_at: "2026-07-26T20:10:00Z",
                }),
                201,
            ),
        );
        const submit = Array.from(
            authenticatedRender.container.querySelectorAll("button"),
        )
            .filter((button) => button.textContent === "Reply")
            .at(-1);
        act(() => {
            submit?.click();
        });
        await flush();
        expect(
            loadCommentDraft({
                slug: "привет-мир",
                kind: "reply",
                threadId: 7,
                userId: 42,
            }),
        ).toBe("");
        act(() => {
            authenticatedRender.root.unmount();
        });
    });

    it("reconciles an optimistic reply with later cursor pages without duplicates", async () => {
        const rootComment = comment({
            reply_count: 25,
            viewer: {
                can_edit: false,
                can_delete: false,
                can_reply: true,
                can_react: true,
            },
        });
        const initialReplies = Array.from({ length: 20 }, (_, index) =>
            comment({
                id: index + 100,
                kind: "reply",
                thread_root_id: 7,
                body: `Reply ${String(index + 1)}`,
                created_at: `2026-07-26T20:00:${String(index).padStart(2, "0")}Z`,
                reply_count: 0,
            }),
        );
        const initialThread: ThreadPage = {
            ...page(initialReplies),
            next: "/api/v1/comments/7/thread/?cursor=next",
            root: rootComment,
        };
        const { container, root } = await renderComments(
            authenticated,
            [rootComment],
            initialThread,
        );
        const open = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Reply",
        );
        act(() => {
            open?.click();
        });
        await flush();

        const created = comment({
            id: 130,
            kind: "reply",
            thread_root_id: 7,
            body: "Optimistic latest",
            created_at: "2026-07-26T20:00:30Z",
            reply_count: 0,
        });
        vi.mocked(fetch).mockResolvedValueOnce(response(created, 201));
        act(() => {
            typeInTextarea(
                container.querySelector("#thread-reply-7"),
                created.body ?? "",
            );
        });
        const send = Array.from(container.querySelectorAll("button"))
            .filter((button) => button.textContent === "Reply")
            .at(-1);
        act(() => {
            send?.click();
        });
        await flush();
        expect(
            container.querySelector('[role="dialog"] h2')?.textContent,
        ).toContain("26 replies");

        const laterReplies = [
            ...Array.from({ length: 5 }, (_, index) =>
                comment({
                    id: index + 120,
                    kind: "reply",
                    thread_root_id: 7,
                    body: `Reply ${String(index + 21)}`,
                    created_at: `2026-07-26T20:00:${String(index + 20).padStart(2, "0")}Z`,
                    reply_count: 0,
                }),
            ),
            { ...created, body: "Fresh latest" },
        ];
        vi.mocked(fetch).mockResolvedValueOnce(
            response({
                ...page(laterReplies),
                root: {
                    ...rootComment,
                    reply_count: 26,
                    last_reply_at: created.created_at,
                },
            }),
        );
        const loadMore = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Load more replies",
        );
        act(() => {
            loadMore?.click();
        });
        await flush();

        const replyIds = Array.from(
            container.querySelectorAll<HTMLElement>(
                ".thread-replies [data-comment-id]",
            ),
        ).map((element) => Number(element.dataset.commentId));
        expect(replyIds).toEqual([
            ...Array.from({ length: 25 }, (_, index) => index + 100),
            130,
        ]);
        expect(new Set(replyIds).size).toBe(replyIds.length);
        expect(container.textContent).toContain("Fresh latest");
        expect(
            container.querySelector('[role="dialog"] h2')?.textContent,
        ).toContain("26 replies");
        act(() => {
            root.unmount();
        });
    });

    it("opens a modal thread, keeps replies level, shows mention, and restores focus", async () => {
        const rootComment = comment({
            viewer: {
                can_edit: false,
                can_delete: false,
                can_reply: true,
                can_react: true,
            },
        });
        const reply = comment({
            id: 10,
            kind: "reply",
            thread_root_id: 7,
            reply_to: { id: 3, display_name: "<Safe author>" },
            body: "Same-level reply",
            reply_count: 0,
        });
        const { container, root } = await renderComments(
            authenticated,
            [rootComment],
            {
                ...page([reply]),
                root: rootComment,
            },
        );
        const trigger = Array.from(container.querySelectorAll("button")).find(
            (button) => button.textContent === "Reply",
        );
        act(() => {
            trigger?.click();
        });
        await flush();

        const dialog = container.querySelector<HTMLElement>('[role="dialog"]');
        expect(dialog?.getAttribute("aria-modal")).toBe("true");
        expect(window.location.search).toBe("?thread=7");
        expect(dialog?.textContent).toContain("Replying to <Safe author>");
        expect(
            dialog?.querySelector('[data-comment-kind="reply"]'),
        ).not.toBeNull();
        expect(document.activeElement?.getAttribute("aria-label")).toBe(
            "Close thread",
        );

        act(() => {
            document.dispatchEvent(
                new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
            );
        });
        await flush();
        expect(container.querySelector('[role="dialog"]')).toBeNull();
        expect(document.activeElement).toBe(trigger);
        act(() => {
            root.unmount();
        });
    });

    it.each(["success", "rollback"] as const)(
        "settles a root reaction in the parent after the thread closes: %s",
        async (settlement) => {
            const toggle = deferred<Response>();
            const rootComment = comment({
                reactions: [reaction(1)],
                viewer: {
                    can_edit: false,
                    can_delete: false,
                    can_reply: true,
                    can_react: true,
                },
            });
            const threadPage: ThreadPage = {
                ...page([]),
                root: rootComment,
            };
            const consoleError = vi
                .spyOn(console, "error")
                .mockImplementation(() => undefined);
            const { container, root } = await renderComments(
                authenticated,
                [rootComment],
                threadPage,
                (url, options) =>
                    options?.method === "POST" && url.includes("/toggle/")
                        ? toggle.promise
                        : null,
            );
            const replyTrigger = Array.from(
                container.querySelectorAll<HTMLButtonElement>("button"),
            ).find(
                (button) =>
                    button.textContent === "Reply" &&
                    button.closest('[role="dialog"]') === null,
            );
            act(() => {
                replyTrigger?.click();
            });
            await flush();
            const dialog = container.querySelector('[role="dialog"]');
            expect(dialog).not.toBeNull();

            act(() => {
                buttonByLabel(
                    dialog ?? container,
                    "Add Clapping reaction",
                )?.click();
            });
            await flush();
            const parentDuringMutation = mainCommentCard(container, 7);
            expect(
                buttonByLabel(
                    parentDuringMutation ?? container,
                    "Remove Clapping reaction",
                )?.disabled,
            ).toBe(true);
            expect(
                buttonByLabel(
                    parentDuringMutation ?? container,
                    "View 2 participants for Clapping",
                ),
            ).toBeDefined();

            act(() => {
                buttonByLabel(container, "Close thread")?.click();
            });
            await flush();
            expect(container.querySelector('[role="dialog"]')).toBeNull();

            await act(async () => {
                if (settlement === "success") {
                    toggle.resolve(
                        response({
                            action: "added",
                            reactions: [reaction(5, true)],
                        }),
                    );
                    await toggle.promise;
                } else {
                    toggle.reject(new Error("offline"));
                    await toggle.promise.catch(() => undefined);
                }
            });
            await flush();

            const parentAfterSettlement = mainCommentCard(container, 7);
            if (settlement === "success") {
                expect(
                    buttonByLabel(
                        parentAfterSettlement ?? container,
                        "View 5 participants for Clapping",
                    ),
                ).toBeDefined();
                expect(
                    buttonByLabel(
                        parentAfterSettlement ?? container,
                        "Remove Clapping reaction",
                    )?.disabled,
                ).toBe(false);
            } else {
                expect(
                    buttonByLabel(
                        parentAfterSettlement ?? container,
                        "View 1 participant for Clapping",
                    ),
                ).toBeDefined();
                expect(
                    buttonByLabel(
                        parentAfterSettlement ?? container,
                        "Add Clapping reaction",
                    )?.disabled,
                ).toBe(false);
            }

            threadPage.root = {
                ...rootComment,
                reactions: [reaction(9, false)],
            };
            act(() => {
                replyTrigger?.click();
            });
            await flush();
            expect(
                buttonByLabel(
                    mainCommentCard(container, 7) ?? container,
                    "View 9 participants for Clapping",
                ),
            ).toBeDefined();
            expect(
                consoleError.mock.calls.some((call) =>
                    call.some(
                        (value) =>
                            typeof value === "string" &&
                            value.toLowerCase().includes("unmounted"),
                    ),
                ),
            ).toBe(false);
            consoleError.mockRestore();
            act(() => {
                root.unmount();
            });
        },
    );

    it("keeps discussions and reactions out of Draft Mode and forbids HTML injection", () => {
        const postPage = readFileSync("app/posts/[slug]/page.tsx", "utf8");
        const commentSources = [
            "../components/comment-card.tsx",
            "../components/comments-section.tsx",
            "../components/thread-panel.tsx",
        ].map((path) => readFileSync(path.replace("../", ""), "utf8"));
        const css = readFileSync("app/globals.css", "utf8");

        expect(postPage).toContain("!preview ? (");
        expect(postPage).toContain(
            "<PostReactions id={post.id} slug={post.slug} />",
        );
        expect(postPage).toContain("<CommentsSection slug={post.slug} />");
        expect(commentSources.join("\n")).not.toContain(
            "dangerouslySetInnerHTML",
        );
        expect(css).toContain("height: 100dvh");
        expect(css).toContain("env(safe-area-inset-bottom)");
        expect(css).toContain("@media (min-width: 48rem)");
    });
});
