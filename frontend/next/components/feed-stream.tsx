"use client";

import { useEffect, useMemo, useState } from "react";

import { PostCard } from "@/components/post-card";
import { ReactionBar } from "@/components/reaction-bar";
import type { PostListItem } from "@/lib/content-contract";
import {
    getPostReactionBatch,
    type ReactionChange,
    type ReactionGroup,
    type ReactionTarget,
} from "@/lib/reactions";
import { postPath } from "@/lib/slug";

function FeedReactionPills({
    initialReactions,
    post,
}: {
    initialReactions: ReactionGroup[];
    post: PostListItem;
}) {
    const [state, setState] = useState({
        pending: false,
        reactions: initialReactions,
    });
    const returnTo = postPath(post.slug);
    const target = useMemo<
        Extract<ReactionTarget, { kind: "post" }> | undefined
    >(
        () =>
            returnTo
                ? {
                      kind: "post",
                      id: post.id,
                      slug: post.slug,
                      returnTo,
                  }
                : undefined,
        [post.id, post.slug, returnTo],
    );

    useEffect(() => {
        setState({ pending: false, reactions: initialReactions });
    }, [initialReactions]);

    if (!target || (state.reactions.length === 0 && !state.pending)) {
        return null;
    }

    function applyChange(change: ReactionChange): void {
        setState({
            pending: change.source === "optimistic",
            reactions: change.reactions,
        });
    }

    return (
        <div className="feed-entry-reactions">
            <ReactionBar
                compact
                initialReactions={state.reactions}
                onChange={applyChange}
                participantsRequireActivation
                slackPills
                target={target}
            />
        </div>
    );
}

export function FeedStream({
    loadReactions,
    posts,
}: {
    loadReactions: boolean;
    posts: PostListItem[];
}) {
    const postIds = useMemo(() => posts.map((post) => post.id), [posts]);
    const idsKey = postIds.join(",");
    const [reactionsByPost, setReactionsByPost] = useState<
        Partial<Record<number, ReactionGroup[]>>
    >({});

    useEffect(() => {
        setReactionsByPost({});
        if (!loadReactions || postIds.length === 0) {
            return;
        }
        const controller = new AbortController();
        void getPostReactionBatch(postIds, controller.signal)
            .then((results) => {
                if (!controller.signal.aborted) {
                    setReactionsByPost(
                        Object.fromEntries(
                            results.map((result) => [
                                result.post_id,
                                result.reactions,
                            ]),
                        ),
                    );
                }
            })
            .catch(() => {
                if (!controller.signal.aborted) {
                    setReactionsByPost({});
                }
            });
        return () => {
            controller.abort();
        };
    }, [idsKey, loadReactions, postIds]);

    return (
        <section className="feed-stream" aria-label="Latest posts">
            {posts.map((post) => {
                const reactions = reactionsByPost[post.id];
                return (
                    <PostCard
                        key={post.id}
                        post={post}
                        reactionContent={
                            reactions !== undefined ? (
                                <FeedReactionPills
                                    initialReactions={reactions}
                                    post={post}
                                />
                            ) : null
                        }
                    />
                );
            })}
        </section>
    );
}
