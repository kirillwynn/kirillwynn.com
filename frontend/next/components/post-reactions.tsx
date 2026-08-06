"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { ReactionBar } from "@/components/reaction-bar";
import { queryKeys } from "@/lib/query-keys";
import {
    getPostReactions,
    type ReactionGroup,
    type ReactionTarget,
} from "@/lib/reactions";

export function PostReactions({ id, slug }: { id: number; slug: string }) {
    const { identityKey, status: authStatus } = useAuth();
    const queryClient = useQueryClient();
    const target: Extract<ReactionTarget, { kind: "post" }> = {
        kind: "post",
        id,
        slug,
        returnTo: `/posts/${slug}`,
    };
    const queryKey = queryKeys.postReactions(identityKey, id);
    const reactionQuery = useQuery<ReactionGroup[]>({
        enabled: authStatus === "ready",
        queryKey,
        queryFn: () => getPostReactions(target),
    });

    return (
        <section
            aria-labelledby="post-reactions-heading"
            className="post-reactions"
        >
            <h2
                className="text-sm font-semibold text-stone-700"
                id="post-reactions-heading"
            >
                Reactions
            </h2>
            {authStatus === "loading" || reactionQuery.isPending ? (
                <p className="mt-2 text-sm text-stone-500" role="status">
                    Loading reactions…
                </p>
            ) : authStatus === "error" || reactionQuery.isError ? (
                <p className="mt-2 text-sm text-red-700" role="alert">
                    Reactions could not be loaded.
                </p>
            ) : (
                <div className="mt-2">
                    <ReactionBar
                        initialReactions={reactionQuery.data}
                        onChange={(change) => {
                            queryClient.setQueryData(
                                queryKey,
                                change.reactions,
                            );
                        }}
                        target={target}
                    />
                </div>
            )}
        </section>
    );
}
