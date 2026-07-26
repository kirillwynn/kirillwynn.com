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
        comments.set(comment.id, comment);
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
