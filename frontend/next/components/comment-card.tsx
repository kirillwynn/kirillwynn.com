"use client";

import { useState } from "react";

import { ReactionBar } from "@/components/reaction-bar";
import {
    CommentApiError,
    deletePublicComment,
    editPublicComment,
    type PublicComment,
} from "@/lib/comments";
import {
    COMMENT_BODY_CODE_POINT_LIMIT,
    codePointLength,
    truncateCodePoints,
} from "@/lib/comment-text";
import type { ReactionChange } from "@/lib/reactions";

function timestamp(value: string): string {
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}

function errorText(error: unknown): string {
    if (error instanceof CommentApiError) {
        if (error.status === 429 && error.retryAfter) {
            return `${error.message} Retry in about ${String(error.retryAfter)} seconds.`;
        }
        return error.message;
    }
    return "The comment could not be changed.";
}

export function CommentCard({
    comment,
    csrfToken,
    onChange,
    onReactionChange,
    onReply,
    onSessionExpired,
    reactionReturnTo,
    slug,
    compact = false,
    allowPendingReply = false,
}: {
    comment: PublicComment;
    csrfToken: string | null;
    onChange: (comment: PublicComment | null) => void;
    onReactionChange?: (commentId: number, change: ReactionChange) => void;
    onReply:
        | ((comment: PublicComment, trigger: HTMLButtonElement) => void)
        | null;
    onSessionExpired: () => void;
    reactionReturnTo: string;
    slug: string;
    compact?: boolean;
    allowPendingReply?: boolean;
}) {
    const [editing, setEditing] = useState(false);
    const [body, setBody] = useState(truncateCodePoints(comment.body ?? ""));
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const canStartPendingReply =
        allowPendingReply && comment.status !== "hidden";

    async function edit(): Promise<void> {
        if (!csrfToken || busy) {
            return;
        }
        setBusy(true);
        setError(null);
        try {
            const changed = await editPublicComment(
                comment.id,
                body,
                csrfToken,
            );
            onChange(changed);
            setEditing(false);
        } catch (caught) {
            if (caught instanceof CommentApiError && caught.status === 403) {
                onSessionExpired();
            }
            setError(errorText(caught));
        } finally {
            setBusy(false);
        }
    }

    async function remove(): Promise<void> {
        if (!csrfToken || busy) {
            return;
        }
        setBusy(true);
        setError(null);
        try {
            await deletePublicComment(comment.id, csrfToken);
            onChange({
                ...comment,
                body: null,
                status: "deleted",
                reactions: [],
                reaction_pending_revision: undefined,
                viewer: {
                    ...comment.viewer,
                    can_edit: false,
                    can_delete: false,
                    can_react: false,
                },
            });
        } catch (caught) {
            if (caught instanceof CommentApiError && caught.status === 403) {
                onSessionExpired();
            }
            setError(errorText(caught));
        } finally {
            setBusy(false);
        }
    }

    return (
        <article
            className={`comment-card ${compact ? "comment-card-compact" : ""}`}
            data-comment-id={comment.id}
            data-comment-kind={comment.kind}
        >
            <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <strong className="text-sm text-stone-900">
                    {comment.author.display_name}
                </strong>
                {comment.author.is_site_author ? (
                    <span className="text-xs font-semibold text-amber-700">
                        Author
                    </span>
                ) : null}
                <time
                    className="text-xs text-stone-500"
                    dateTime={comment.created_at}
                >
                    {timestamp(comment.created_at)}
                </time>
                {comment.edited_at ? (
                    <span className="text-xs text-stone-500">edited</span>
                ) : null}
            </header>

            {comment.reply_to ? (
                <p className="mt-2 text-xs font-medium text-stone-500">
                    Replying to {comment.reply_to.display_name}
                </p>
            ) : null}

            {editing ? (
                <div className="mt-3">
                    <label
                        className="sr-only"
                        htmlFor={`edit-comment-${String(comment.id)}`}
                    >
                        Edit comment
                    </label>
                    <textarea
                        id={`edit-comment-${String(comment.id)}`}
                        className="comment-textarea"
                        onChange={(event) => {
                            setBody(truncateCodePoints(event.target.value));
                        }}
                        rows={4}
                        value={body}
                    />
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="mr-auto text-xs text-stone-500">
                            {codePointLength(body)}/
                            {COMMENT_BODY_CODE_POINT_LIMIT}
                        </span>
                        <button
                            className="comment-action"
                            disabled={busy}
                            onClick={() => void edit()}
                            type="button"
                        >
                            Save
                        </button>
                        <button
                            className="comment-action"
                            disabled={busy}
                            onClick={() => {
                                setBody(truncateCodePoints(comment.body ?? ""));
                                setEditing(false);
                                setError(null);
                            }}
                            type="button"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-stone-700">
                    {comment.status === "deleted"
                        ? "[deleted]"
                        : comment.status === "hidden"
                          ? "[hidden]"
                          : comment.body}
                </p>
            )}

            {!editing ? (
                <div className="mt-3 flex flex-wrap items-center gap-1">
                    {onReply &&
                    (comment.viewer.can_reply ||
                        (!compact &&
                            (comment.reply_count > 0 ||
                                canStartPendingReply))) ? (
                        <button
                            className="comment-action"
                            onClick={(event) => {
                                onReply(comment, event.currentTarget);
                            }}
                            type="button"
                        >
                            {comment.viewer.can_reply || canStartPendingReply
                                ? "Reply"
                                : "View thread"}
                        </button>
                    ) : null}
                    {comment.viewer.can_edit ? (
                        <button
                            className="comment-action"
                            onClick={() => {
                                setBody(truncateCodePoints(comment.body ?? ""));
                                setEditing(true);
                            }}
                            type="button"
                        >
                            Edit
                        </button>
                    ) : null}
                    {comment.viewer.can_delete ? (
                        <button
                            className="comment-action"
                            disabled={busy}
                            onClick={() => void remove()}
                            type="button"
                        >
                            Delete
                        </button>
                    ) : null}
                    {!compact && comment.reply_count > 0 ? (
                        <span className="ml-1 text-xs text-stone-500">
                            {comment.reply_count}{" "}
                            {comment.reply_count === 1 ? "reply" : "replies"}
                            {comment.last_reply_at
                                ? ` · last ${timestamp(comment.last_reply_at)}`
                                : ""}
                        </span>
                    ) : null}
                </div>
            ) : null}

            {!editing && comment.status === "visible" ? (
                <div className="mt-2">
                    <ReactionBar
                        initialReactions={comment.reactions}
                        onChange={(change) => {
                            onReactionChange?.(comment.id, change);
                        }}
                        target={{
                            kind: "comment",
                            id: comment.id,
                            slug,
                            returnTo: reactionReturnTo,
                        }}
                    />
                </div>
            ) : null}

            {error ? (
                <p className="mt-2 text-sm text-red-700" role="alert">
                    {error}
                </p>
            ) : null}
        </article>
    );
}
