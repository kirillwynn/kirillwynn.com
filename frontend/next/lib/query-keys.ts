export const queryKeys = {
    reactionCatalog: ["public", "reaction-catalog"] as const,
    feed(query: string) {
        return ["public", "feed", query] as const;
    },
    feedReactionBatch(identity: string, postIds: number[]) {
        return [
            "viewer",
            identity,
            "feed-reactions",
            postIds.join(","),
        ] as const;
    },
    postReactions(identity: string, postId: number) {
        return ["viewer", identity, "post-reactions", postId] as const;
    },
    reactionParticipants(
        identity: string,
        targetKind: "post" | "comment",
        targetId: number,
        reactionId: string,
        cursor: string | null,
    ) {
        return [
            "viewer",
            identity,
            "reaction-participants",
            targetKind,
            targetId,
            reactionId,
            cursor ?? "first",
        ] as const;
    },
    comments(identity: string, slug: string, cursor: string | null) {
        return [
            "viewer",
            identity,
            "comments",
            slug,
            cursor ?? "first",
        ] as const;
    },
    thread(identity: string, rootId: number, cursor: string | null) {
        return [
            "viewer",
            identity,
            "thread",
            rootId,
            cursor ?? "first",
        ] as const;
    },
};
