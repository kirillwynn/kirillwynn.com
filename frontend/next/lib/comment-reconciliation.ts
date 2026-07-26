import type { PublicComment } from "@/lib/comments";

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
        if (
            comment.status === "visible" &&
            existing?.reactions_updated_locally &&
            !comment.reactions_updated_locally
        ) {
            comments.set(comment.id, {
                ...comment,
                reactions: existing.reactions,
                reactions_updated_locally: true,
            });
        } else {
            comments.set(comment.id, {
                ...comment,
                reactions:
                    comment.status === "visible" ? comment.reactions : [],
                reactions_updated_locally:
                    comment.status === "visible"
                        ? comment.reactions_updated_locally
                        : false,
            });
        }
    }
    return Array.from(comments.values()).sort(compare);
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
