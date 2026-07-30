"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { ReactionDescriptor } from "@/lib/reactions";

export function ReactionImage({
    animate = true,
    className,
    deferUntilVisible = false,
    reaction,
}: {
    animate?: boolean;
    className?: string;
    deferUntilVisible?: boolean;
    reaction: ReactionDescriptor;
}) {
    const rootRef = useRef<HTMLSpanElement>(null);
    const [visible, setVisible] = useState(false);
    const [reducedMotion, setReducedMotion] = useState(true);
    const [failedSources, setFailedSources] = useState<Set<string>>(
        () => new Set(),
    );

    useEffect(() => {
        if (typeof window.matchMedia !== "function") {
            setReducedMotion(false);
            return;
        }
        const query = window.matchMedia("(prefers-reduced-motion: reduce)");
        const update = (): void => {
            setReducedMotion(query.matches);
        };
        update();
        query.addEventListener("change", update);
        return () => {
            query.removeEventListener("change", update);
        };
    }, []);

    useEffect(() => {
        const root = rootRef.current;
        if (!root || typeof IntersectionObserver === "undefined") {
            setVisible(true);
            return;
        }
        const observer = new IntersectionObserver(
            ([entry]) => {
                setVisible(entry.isIntersecting);
            },
            { rootMargin: "0px" },
        );
        observer.observe(root);
        return () => {
            observer.disconnect();
        };
    }, []);

    useEffect(() => {
        setFailedSources(new Set());
    }, [reaction.version]);

    const shouldLoad = !deferUntilVisible || visible;
    const preferredSource = shouldLoad
        ? reaction.kind === "animated" && animate && visible && !reducedMotion
            ? reaction.asset_url
            : reaction.poster_url
        : null;
    const source = useMemo(() => {
        if (!preferredSource) {
            return null;
        }
        if (!failedSources.has(preferredSource)) {
            return preferredSource;
        }
        if (!failedSources.has(reaction.poster_url)) {
            return reaction.poster_url;
        }
        return null;
    }, [failedSources, preferredSource, reaction.poster_url]);

    return (
        <span
            className={`reaction-image ${className ?? ""}`}
            data-animated={
                source === reaction.asset_url && reaction.kind === "animated"
                    ? "true"
                    : "false"
            }
            ref={rootRef}
        >
            {!shouldLoad ? null : source ? (
                // The containing button owns the accessible reaction name.
                <img
                    alt=""
                    decoding="async"
                    height={reaction.height}
                    loading="lazy"
                    onError={() => {
                        setFailedSources((current) => {
                            const next = new Set(current);
                            next.add(source);
                            return next;
                        });
                    }}
                    src={source}
                    width={reaction.width}
                />
            ) : (
                <span className="reaction-image__fallback">
                    {reaction.name}
                </span>
            )}
        </span>
    );
}
