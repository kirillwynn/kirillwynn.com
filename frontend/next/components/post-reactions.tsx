"use client";

import { useEffect, useState } from "react";

import { ReactionBar } from "@/components/reaction-bar";
import {
    getPostReactions,
    type ReactionGroup,
    type ReactionTarget,
} from "@/lib/reactions";

export function PostReactions({ id, slug }: { id: number; slug: string }) {
    const target: Extract<ReactionTarget, { kind: "post" }> = {
        kind: "post",
        id,
        slug,
        returnTo: `/posts/${slug}`,
    };
    const [reactions, setReactions] = useState<ReactionGroup[]>([]);
    const [status, setStatus] = useState<"loading" | "ready" | "error">(
        "loading",
    );

    useEffect(() => {
        let active = true;
        void getPostReactions({
            kind: "post",
            id,
            slug,
            returnTo: `/posts/${slug}`,
        })
            .then((groups) => {
                if (active) {
                    setReactions(groups);
                    setStatus("ready");
                }
            })
            .catch(() => {
                if (active) {
                    setStatus("error");
                }
            });
        return () => {
            active = false;
        };
    }, [id, slug]);

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
            {status === "loading" ? (
                <p className="mt-2 text-sm text-stone-500" role="status">
                    Loading reactions…
                </p>
            ) : status === "error" ? (
                <p className="mt-2 text-sm text-red-700" role="alert">
                    Reactions could not be loaded.
                </p>
            ) : (
                <div className="mt-2">
                    <ReactionBar
                        initialReactions={reactions}
                        onChange={(change) => {
                            setReactions(change.reactions);
                        }}
                        slackPills
                        target={target}
                    />
                </div>
            )}
        </section>
    );
}
