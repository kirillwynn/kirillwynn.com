"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { CommentCard } from "@/components/comment-card";
import { ThreadPanel } from "@/components/thread-panel";
import {
    clearCommentDraft,
    loadCommentDraft,
    saveCommentDraft,
} from "@/lib/comment-drafts";
import {
    applyCommentReactionChange,
    applyCommentReactionChangeToList,
    reconcileComment,
    reconcileRoots,
} from "@/lib/comment-reconciliation";
import {
    COMMENT_BODY_CODE_POINT_LIMIT,
    codePointLength,
    truncateCodePoints,
} from "@/lib/comment-text";
import {
    CommentApiError,
    createComment,
    getComments,
    getThread,
    type PublicComment,
} from "@/lib/comments";
import type { ReactionChange } from "@/lib/reactions";

function returnTo(slug: string): string {
    return `/posts/${slug}`;
}

function errorMessage(error: unknown): string {
    if (error instanceof CommentApiError) {
        if (error.status === 429 && error.retryAfter) {
            return `${error.message} Retry in about ${String(error.retryAfter)} seconds.`;
        }
        return error.message;
    }
    return "Comments could not be loaded.";
}

function queryThreadId(): number | null {
    const value = new URL(window.location.href).searchParams.get("thread");
    return value && /^\d+$/.test(value) && Number(value) > 0
        ? Number(value)
        : null;
}

export function CommentsSection({ slug }: { slug: string }) {
    const { me, refresh, status: authStatus } = useAuth();
    const [comments, setComments] = useState<PublicComment[]>([]);
    const [next, setNext] = useState<string | null>(null);
    const [status, setStatus] = useState<"loading" | "ready" | "error">(
        "loading",
    );
    const [error, setError] = useState<string | null>(null);
    const [body, setBody] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [openRoot, setOpenRoot] = useState<PublicComment | null>(null);
    const triggerRef = useRef<HTMLButtonElement | null>(null);
    const pushedThreadRef = useRef(false);
    const handledInitialThreadRef = useRef(false);
    const user = me?.authenticated ? me.user : null;

    const load = useCallback(
        async (cursor?: string, append = false) => {
            if (!append) {
                setStatus("loading");
            }
            setError(null);
            try {
                const page = await getComments(slug, cursor);
                setComments((current) =>
                    reconcileRoots(append ? current : [], page.results),
                );
                setNext(page.next);
                setStatus("ready");
            } catch (caught) {
                setError(errorMessage(caught));
                setStatus("error");
            }
        },
        [slug],
    );

    useEffect(() => {
        void load();
    }, [load]);

    useEffect(() => {
        if (authStatus === "loading") {
            return;
        }
        setBody(
            loadCommentDraft({
                slug,
                kind: "comment",
                userId: user?.id ?? null,
            }),
        );
    }, [authStatus, slug, user?.id]);

    const replaceComment = useCallback((changed: PublicComment | null) => {
        if (!changed) {
            return;
        }
        setComments((current) => reconcileRoots(current, [changed]));
        setOpenRoot((current) =>
            current?.id === changed.id
                ? reconcileComment(current, changed)
                : current,
        );
    }, []);

    const changeCommentReaction = useCallback(
        (commentId: number, change: ReactionChange) => {
            setComments((current) =>
                applyCommentReactionChangeToList(current, commentId, change),
            );
            setOpenRoot((current) =>
                current?.id === commentId
                    ? applyCommentReactionChange(current, change)
                    : current,
            );
        },
        [],
    );

    const closeFromHistory = useCallback(() => {
        setOpenRoot(null);
        pushedThreadRef.current = false;
        triggerRef.current?.focus();
    }, []);

    useEffect(() => {
        function popstate(): void {
            const threadId = queryThreadId();
            if (threadId === null) {
                closeFromHistory();
                return;
            }
            const root = comments.find((comment) => comment.id === threadId);
            if (root) {
                setOpenRoot(root);
            }
        }
        window.addEventListener("popstate", popstate);
        return () => {
            window.removeEventListener("popstate", popstate);
        };
    }, [closeFromHistory, comments]);

    useEffect(() => {
        if (status !== "ready" || handledInitialThreadRef.current) {
            return;
        }
        handledInitialThreadRef.current = true;
        const threadId = queryThreadId();
        if (threadId === null) {
            return;
        }
        const root = comments.find((comment) => comment.id === threadId);
        if (root) {
            setOpenRoot(root);
            return;
        }
        void getThread(threadId)
            .then((thread) => {
                setOpenRoot(thread.root);
            })
            .catch(() => {
                const url = new URL(window.location.href);
                url.searchParams.delete("thread");
                window.history.replaceState(
                    {},
                    "",
                    `${url.pathname}${url.search}`,
                );
            });
    }, [comments, status]);

    function openThread(
        comment: PublicComment,
        trigger: HTMLButtonElement,
    ): void {
        triggerRef.current = trigger;
        setOpenRoot(comment);
        const url = new URL(window.location.href);
        url.searchParams.set("thread", String(comment.id));
        window.history.pushState({}, "", `${url.pathname}${url.search}`);
        pushedThreadRef.current = true;
    }

    function closeThread(): void {
        if (pushedThreadRef.current && queryThreadId() !== null) {
            closeFromHistory();
            window.history.back();
            return;
        }
        const url = new URL(window.location.href);
        url.searchParams.delete("thread");
        window.history.replaceState({}, "", `${url.pathname}${url.search}`);
        closeFromHistory();
    }

    function updateBody(value: string): void {
        const normalized = truncateCodePoints(value);
        setBody(normalized);
        saveCommentDraft({
            slug,
            kind: "comment",
            userId: user?.id ?? null,
            body: normalized,
        });
    }

    function discardDraft(): void {
        setBody("");
        clearCommentDraft({
            slug,
            kind: "comment",
            userId: user?.id ?? null,
        });
    }

    async function submit(): Promise<void> {
        if (!user || !me?.csrf_token || !body.trim() || submitting) {
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            const comment = await createComment(slug, body, me.csrf_token);
            setComments((current) => reconcileRoots(current, [comment]));
            setBody("");
            clearCommentDraft({
                slug,
                kind: "comment",
                userId: user.id,
            });
        } catch (caught) {
            if (caught instanceof CommentApiError && caught.status === 403) {
                saveCommentDraft({
                    slug,
                    kind: "comment",
                    userId: null,
                    body,
                });
                await refresh();
            }
            setError(errorMessage(caught));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <section
            aria-labelledby="comments-heading"
            className="comments-section"
        >
            <div className="flex items-center justify-between gap-4">
                <div>
                    <p className="eyebrow">Discussion</p>
                    <h2
                        className="mt-2 text-2xl font-semibold tracking-tight text-stone-950"
                        id="comments-heading"
                    >
                        Comments
                    </h2>
                </div>
            </div>

            <div className="mt-6 rounded-xl border border-stone-200 bg-white p-4 sm:p-5">
                {authStatus === "loading" ? (
                    <p className="text-sm text-stone-500">Loading account…</p>
                ) : user && !user.can_interact ? (
                    <p className="text-sm text-stone-600">
                        This account is read-only. You can still read comments
                        and threads.
                    </p>
                ) : (
                    <>
                        <label
                            className="text-sm font-semibold text-stone-800"
                            htmlFor="new-comment"
                        >
                            Add a comment
                        </label>
                        <textarea
                            className="comment-textarea mt-2"
                            id="new-comment"
                            onChange={(event) => {
                                updateBody(event.target.value);
                            }}
                            placeholder="Write a plain-text comment"
                            rows={4}
                            value={body}
                        />
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                            <span className="text-xs text-stone-500">
                                {codePointLength(body)}/
                                {COMMENT_BODY_CODE_POINT_LIMIT}
                            </span>
                            <div className="flex gap-2">
                                {body ? (
                                    <button
                                        className="comment-action"
                                        onClick={discardDraft}
                                        type="button"
                                    >
                                        Discard
                                    </button>
                                ) : null}
                                {user ? (
                                    <button
                                        className="button-link"
                                        disabled={submitting || !body.trim()}
                                        onClick={() => void submit()}
                                        type="button"
                                    >
                                        {submitting ? "Posting…" : "Comment"}
                                    </button>
                                ) : (
                                    <a
                                        className="button-link"
                                        href={`/login?next=${encodeURIComponent(returnTo(slug))}`}
                                        onClick={() => {
                                            saveCommentDraft({
                                                slug,
                                                kind: "comment",
                                                userId: null,
                                                body,
                                            });
                                        }}
                                    >
                                        Login to comment
                                    </a>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </div>

            {error ? (
                <div className="mt-5" role="alert">
                    <p className="text-sm text-red-700">{error}</p>
                    {status === "error" ? (
                        <button
                            className="button-link mt-3"
                            onClick={() => void load()}
                            type="button"
                        >
                            Retry comments
                        </button>
                    ) : null}
                </div>
            ) : null}

            {status === "loading" ? (
                <p className="mt-6 text-sm text-stone-500" role="status">
                    Loading comments…
                </p>
            ) : null}
            {status === "ready" && comments.length === 0 ? (
                <p className="mt-6 text-sm text-stone-500">
                    No comments yet. Start the discussion.
                </p>
            ) : null}

            <div className="mt-6 space-y-4">
                {comments.map((comment) => (
                    <CommentCard
                        allowPendingReply={
                            authStatus === "ready" && user === null
                        }
                        comment={comment}
                        csrfToken={me?.csrf_token ?? null}
                        key={comment.id}
                        onChange={replaceComment}
                        onReactionChange={changeCommentReaction}
                        onReply={openThread}
                        onSessionExpired={() => void refresh()}
                        reactionReturnTo={returnTo(slug)}
                        slug={slug}
                    />
                ))}
            </div>

            {next ? (
                <button
                    className="button-link mt-5"
                    onClick={() => void load(next, true)}
                    type="button"
                >
                    Load more comments
                </button>
            ) : null}

            {openRoot ? (
                <ThreadPanel
                    initialRoot={openRoot}
                    onClose={closeThread}
                    onRootChange={replaceComment}
                    onRootReactionChange={changeCommentReaction}
                    slug={slug}
                />
            ) : null}
        </section>
    );
}
