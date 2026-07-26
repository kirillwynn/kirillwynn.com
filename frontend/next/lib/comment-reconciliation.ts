import type { PublicComment } from "@/lib/comments";
import type { ReactionChange } from "@/lib/reactions";

function timestamp(value: string): number {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? 0 : parsed;
}

function compareAscending(left: PublicComment, right: PublicComment): number {
    const byCreatedAt =
        timestamp(left.created_at) - timestamp(right.created_at);
    if (byCreatedAt) {
        return byCreatedAt;
    }
    if (left.created_at !== right.created_at) {
        return left.created_at < right.created_at ? -1 : 1;
    }
    return left.id - right.id;
}

function reconcile(
    current: PublicComment[],
    incoming: PublicComment[],
    compare: (left: PublicComment, right: PublicComment) => number,
): PublicComment[] {
    const comments = new Map<number, PublicComment>();
    for (const comment of current) {
        comments.set(comment.id, comment);
    }
    for (const comment of incoming) {
        const existing = comments.get(comment.id);
        comments.set(comment.id, reconcileComment(existing, comment));
    }
    return Array.from(comments.values()).sort(compare);
}

export function reconcileComment(
    current: PublicComment | undefined,
    incoming: PublicComment,
): PublicComment {
    if (incoming.status !== "visible") {
        return {
            ...incoming,
            reactions: [],
            reaction_pending_revision: undefined,
        };
    }
    if (
        current?.status === "visible" &&
        current.reaction_pending_revision !== undefined
    ) {
        return {
            ...incoming,
            reactions: current.reactions,
            reaction_pending_revision: current.reaction_pending_revision,
        };
    }
    return {
        ...incoming,
        reaction_pending_revision: undefined,
    };
}

export function applyCommentReactionChange(
    comment: PublicComment,
    change: ReactionChange,
): PublicComment {
    if (comment.status !== "visible") {
        return {
            ...comment,
            reactions: [],
            reaction_pending_revision: undefined,
        };
    }
    if (change.source === "optimistic") {
        if (
            comment.reaction_pending_revision !== undefined &&
            change.revision < comment.reaction_pending_revision
        ) {
            return comment;
        }
        return {
            ...comment,
            reactions: change.reactions,
            reaction_pending_revision: change.revision,
        };
    }
    if (comment.reaction_pending_revision !== change.revision) {
        return comment;
    }
    return {
        ...comment,
        reactions: change.reactions,
        reaction_pending_revision: undefined,
    };
}

export function applyCommentReactionChangeToList(
    comments: PublicComment[],
    commentId: number,
    change: ReactionChange,
): PublicComment[] {
    return comments.map((comment) =>
        comment.id === commentId
            ? applyCommentReactionChange(comment, change)
            : comment,
    );
}

export function reconcileRoots(
    current: PublicComment[],
    incoming: PublicComment[],
): PublicComment[] {
    return reconcile(current, incoming, (left, right) =>
        compareAscending(right, left),
    );
}

export function reconcileReplies(
    current: PublicComment[],
    incoming: PublicComment[],
): PublicComment[] {
    return reconcile(current, incoming, compareAscending);
}
