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
    createComment,
    createThreadReply,
    deletePublicComment,
    editPublicComment,
    getComments,
    type CommentPage,
    type PublicComment,
    type ThreadPage,
} from "@/lib/comments";

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
        viewer: {
            can_edit: false,
            can_delete: false,
            can_reply: false,
        },
        ...overrides,
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

async function renderComments(
    me: MeResponse,
    roots: PublicComment[],
    thread?: ThreadPage,
): Promise<{ container: HTMLDivElement; root: Root }> {
    vi.mocked(fetch).mockImplementation((input) => {
        const url =
            typeof input === "string"
                ? input
                : input instanceof URL
                  ? input.href
                  : input.url;
        if (url === "/api/me/") {
            return Promise.resolve(response(me));
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
        expect(container.querySelector("textarea")).toBeNull();
        act(() => {
            root.unmount();
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

    it("opens a modal thread, keeps replies level, shows mention, and restores focus", async () => {
        const rootComment = comment({
            viewer: {
                can_edit: false,
                can_delete: false,
                can_reply: true,
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

    it("keeps comments out of Draft Mode and forbids HTML/reaction shortcuts", () => {
        const postPage = readFileSync("app/posts/[slug]/page.tsx", "utf8");
        const commentSources = [
            "../components/comment-card.tsx",
            "../components/comments-section.tsx",
            "../components/thread-panel.tsx",
        ].map((path) => readFileSync(path.replace("../", ""), "utf8"));
        const css = readFileSync("app/globals.css", "utf8");

        expect(postPage).toContain(
            "!preview ? <CommentsSection slug={post.slug} /> : null",
        );
        expect(commentSources.join("\n")).not.toContain(
            "dangerouslySetInnerHTML",
        );
        expect(commentSources.join("\n").toLowerCase()).not.toContain(
            "reaction",
        );
        expect(css).toContain("height: 100dvh");
        expect(css).toContain("env(safe-area-inset-bottom)");
        expect(css).toContain("@media (min-width: 48rem)");
    });
});
