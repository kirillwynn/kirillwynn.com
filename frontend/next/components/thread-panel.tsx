"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { CommentCard } from "@/components/comment-card";
import {
    clearCommentDraft,
    loadCommentDraft,
    saveCommentDraft,
} from "@/lib/comment-drafts";
import {
    applyCommentReactionChange,
    applyCommentReactionChangeToList,
    reconcileComment,
    reconcileReplies,
} from "@/lib/comment-reconciliation";
import {
    COMMENT_BODY_CODE_POINT_LIMIT,
    codePointLength,
    truncateCodePoints,
} from "@/lib/comment-text";
import {
    CommentApiError,
    createThreadReply,
    getThread,
    type PublicComment,
} from "@/lib/comments";
import type { ReactionChange } from "@/lib/reactions";

function returnTo(slug: string, threadId: number): string {
    return `/posts/${slug}?thread=${String(threadId)}`;
}

function message(error: unknown): string {
    if (error instanceof CommentApiError) {
        if (error.status === 429 && error.retryAfter) {
            return `${error.message} Retry in about ${String(error.retryAfter)} seconds.`;
        }
        return error.message;
    }
    return "The thread could not be loaded.";
}

export function ThreadPanel({
    initialRoot,
    slug,
    onClose,
    onRootChange,
    onRootReactionChange,
}: {
    initialRoot: PublicComment;
    slug: string;
    onClose: () => void;
    onRootChange: (root: PublicComment) => void;
    onRootReactionChange: (commentId: number, change: ReactionChange) => void;
}) {
    const { me, refresh, status: authStatus } = useAuth();
    const [root, setRoot] = useState(initialRoot);
    const [replies, setReplies] = useState<PublicComment[]>([]);
    const [next, setNext] = useState<string | null>(null);
    const [status, setStatus] = useState<"loading" | "ready" | "error">(
        "loading",
    );
    const [error, setError] = useState<string | null>(null);
    const [body, setBody] = useState("");
    const [target, setTarget] = useState<PublicComment>(initialRoot);
    const [sending, setSending] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);
    const closeRef = useRef<HTMLButtonElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const user = me?.authenticated ? me.user : null;
    const canInteract = Boolean(user?.can_interact);
    const canReplyToThread = user
        ? canInteract && root.viewer.can_reply
        : root.status !== "hidden";

    useEffect(() => {
        let active = true;
        void getThread(initialRoot.id)
            .then((page) => {
                if (!active) {
                    return;
                }
                setRoot((current) => reconcileComment(current, page.root));
                setReplies(reconcileReplies([], page.results));
                setNext(page.next);
                setStatus("ready");
                onRootChange(page.root);
            })
            .catch((caught: unknown) => {
                if (active) {
                    setError(message(caught));
                    setStatus("error");
                }
            });
        return () => {
            active = false;
        };
    }, [initialRoot.id, onRootChange]);

    useEffect(() => {
        if (authStatus === "loading") {
            return;
        }
        setBody(
            loadCommentDraft({
                slug,
                kind: "reply",
                threadId: root.id,
                userId: user?.id ?? null,
            }),
        );
    }, [authStatus, root.id, slug, user?.id]);

    useEffect(() => {
        closeRef.current?.focus();
        const panel = panelRef.current;
        function keydown(event: KeyboardEvent): void {
            if (event.key === "Escape") {
                event.preventDefault();
                onClose();
                return;
            }
            if (event.key !== "Tab" || !panel) {
                return;
            }
            const focusable = Array.from(
                panel.querySelectorAll<HTMLElement>(
                    'a[href], button:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
                ),
            );
            if (focusable.length === 0) {
                return;
            }
            const first = focusable[0];
            const last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
        document.addEventListener("keydown", keydown);
        return () => {
            document.removeEventListener("keydown", keydown);
        };
    }, [onClose]);

    function changeRoot(changed: PublicComment | null): void {
        if (!changed) {
            return;
        }
        setRoot((current) => reconcileComment(current, changed));
        onRootChange(changed);
    }

    function changeReply(changed: PublicComment | null): void {
        if (!changed) {
            return;
        }
        setReplies((current) => reconcileReplies(current, [changed]));
    }

    function changeRootReaction(
        commentId: number,
        change: ReactionChange,
    ): void {
        setRoot((current) =>
            current.id === commentId
                ? applyCommentReactionChange(current, change)
                : current,
        );
        onRootReactionChange(commentId, change);
    }

    function changeReplyReaction(
        commentId: number,
        change: ReactionChange,
    ): void {
        setReplies((current) =>
            applyCommentReactionChangeToList(current, commentId, change),
        );
    }

    async function loadMore(): Promise<void> {
        if (!next) {
            return;
        }
        try {
            const page = await getThread(root.id, next);
            setReplies((current) => reconcileReplies(current, page.results));
            setRoot((current) => reconcileComment(current, page.root));
            onRootChange(page.root);
            setNext(page.next);
        } catch (caught) {
            setError(message(caught));
        }
    }

    async function sendReply(): Promise<void> {
        if (!user || !me?.csrf_token || !body.trim() || sending) {
            return;
        }
        setSending(true);
        setError(null);
        try {
            const reply = await createThreadReply(
                target.id,
                body,
                me.csrf_token,
            );
            const isNew = !replies.some((current) => current.id === reply.id);
            setReplies((current) => reconcileReplies(current, [reply]));
            const changedRoot = isNew
                ? {
                      ...root,
                      reply_count: root.reply_count + 1,
                      last_reply_at: reply.created_at,
                  }
                : root;
            setRoot((current) =>
                isNew
                    ? {
                          ...current,
                          reply_count: current.reply_count + 1,
                          last_reply_at: reply.created_at,
                      }
                    : current,
            );
            onRootChange(changedRoot);
            setBody("");
            setTarget(root);
            clearCommentDraft({
                slug,
                kind: "reply",
                threadId: root.id,
                userId: user.id,
            });
        } catch (caught) {
            if (caught instanceof CommentApiError && caught.status === 403) {
                saveCommentDraft({
                    slug,
                    kind: "reply",
                    threadId: root.id,
                    userId: null,
                    body,
                });
                await refresh();
            }
            setError(message(caught));
        } finally {
            setSending(false);
        }
    }

    function updateBody(value: string): void {
        const normalized = truncateCodePoints(value);
        setBody(normalized);
        saveCommentDraft({
            slug,
            kind: "reply",
            threadId: root.id,
            userId: user?.id ?? null,
            body: normalized,
        });
    }

    function discardDraft(): void {
        setBody("");
        clearCommentDraft({
            slug,
            kind: "reply",
            threadId: root.id,
            userId: user?.id ?? null,
        });
    }

    return (
        <div className="thread-backdrop" onMouseDown={onClose}>
            <div
                aria-label={`Thread for comment by ${root.author.display_name}`}
                aria-modal="true"
                className="thread-panel"
                onMouseDown={(event) => {
                    event.stopPropagation();
                }}
                ref={panelRef}
                role="dialog"
            >
                <header className="thread-panel-header">
                    <div>
                        <p className="eyebrow">Thread</p>
                        <h2 className="mt-1 text-lg font-semibold text-stone-950">
                            {root.reply_count}{" "}
                            {root.reply_count === 1 ? "reply" : "replies"}
                        </h2>
                    </div>
                    <button
                        aria-label="Close thread"
                        className="comment-action"
                        onClick={onClose}
                        ref={closeRef}
                        type="button"
                    >
                        Close
                    </button>
                </header>

                <div className="thread-root">
                    <CommentCard
                        comment={root}
                        compact
                        csrfToken={me?.csrf_token ?? null}
                        onChange={changeRoot}
                        onReactionChange={changeRootReaction}
                        onReply={(comment) => {
                            setTarget(comment);
                            textareaRef.current?.focus();
                        }}
                        onSessionExpired={() => void refresh()}
                        reactionReturnTo={returnTo(slug, root.id)}
                        slug={slug}
                    />
                </div>

                <div className="thread-replies" tabIndex={0}>
                    {status === "loading" ? (
                        <p className="text-sm text-stone-500" role="status">
                            Loading replies…
                        </p>
                    ) : null}
                    {status === "error" ? (
                        <button
                            className="button-link"
                            onClick={() => {
                                window.location.reload();
                            }}
                            type="button"
                        >
                            Retry thread
                        </button>
                    ) : null}
                    {replies.map((reply) => (
                        <CommentCard
                            comment={reply}
                            compact
                            csrfToken={me?.csrf_token ?? null}
                            key={reply.id}
                            onChange={changeReply}
                            onReactionChange={changeReplyReaction}
                            onReply={(selected) => {
                                setTarget(selected);
                                textareaRef.current?.focus();
                            }}
                            onSessionExpired={() => void refresh()}
                            reactionReturnTo={returnTo(slug, root.id)}
                            slug={slug}
                        />
                    ))}
                    {next ? (
                        <button
                            className="button-link"
                            onClick={() => void loadMore()}
                            type="button"
                        >
                            Load more replies
                        </button>
                    ) : null}
                </div>

                <footer className="thread-composer">
                    {error ? (
                        <p className="mb-2 text-sm text-red-700" role="alert">
                            {error}
                        </p>
                    ) : null}
                    {authStatus === "loading" ? (
                        <p className="text-sm text-stone-500">
                            Loading account…
                        </p>
                    ) : !canReplyToThread ? (
                        <p className="text-sm text-stone-600">
                            This thread is read-only. Existing replies remain
                            visible.
                        </p>
                    ) : (
                        <>
                            <div className="mb-2 flex items-center justify-between gap-2 text-xs text-stone-500">
                                <span>
                                    Replying to {target.author.display_name}
                                </span>
                                {target.id !== root.id ? (
                                    <button
                                        className="underline"
                                        onClick={() => {
                                            setTarget(root);
                                        }}
                                        type="button"
                                    >
                                        Clear mention
                                    </button>
                                ) : null}
                            </div>
                            <label
                                className="sr-only"
                                htmlFor={`thread-reply-${String(root.id)}`}
                            >
                                Reply to thread
                            </label>
                            <textarea
                                className="comment-textarea"
                                id={`thread-reply-${String(root.id)}`}
                                onChange={(event) => {
                                    updateBody(event.target.value);
                                }}
                                placeholder="Write a reply"
                                ref={textareaRef}
                                rows={3}
                                value={body}
                            />
                            <div className="mt-2 flex items-center justify-between gap-2">
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
                                            disabled={sending || !body.trim()}
                                            onClick={() => void sendReply()}
                                            type="button"
                                        >
                                            {sending ? "Sending…" : "Reply"}
                                        </button>
                                    ) : (
                                        <a
                                            className="button-link"
                                            href={`/login?next=${encodeURIComponent(returnTo(slug, root.id))}`}
                                            onClick={() => {
                                                saveCommentDraft({
                                                    slug,
                                                    kind: "reply",
                                                    threadId: root.id,
                                                    userId: null,
                                                    body,
                                                });
                                            }}
                                        >
                                            Login to reply
                                        </a>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </footer>
            </div>
        </div>
    );
}
