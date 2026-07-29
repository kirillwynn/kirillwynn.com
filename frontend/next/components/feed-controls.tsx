"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { AvailableTag } from "@/lib/content-contract";
import { feedHref, type FeedState } from "@/lib/feed-state";

const SEARCH_DEBOUNCE_MS = 300;

export function FeedControls({
    state,
    tags,
}: {
    state: FeedState;
    tags: AvailableTag[];
}) {
    const router = useRouter();
    const [query, setQuery] = useState(state.q ?? "");
    const timerRef = useRef<number | null>(null);
    const timerGenerationRef = useRef(0);
    const composingRef = useRef(false);
    const currentHref = feedHref(state);
    const serverQuery = state.q ?? "";
    const lastNavigationRef = useRef(currentHref);
    const previousServerHrefRef = useRef(currentHref);

    useEffect(() => {
        if (previousServerHrefRef.current === currentHref) {
            return;
        }
        previousServerHrefRef.current = currentHref;

        if (
            currentHref === lastNavigationRef.current &&
            timerRef.current !== null
        ) {
            return;
        }

        timerGenerationRef.current += 1;
        if (timerRef.current !== null) {
            window.clearTimeout(timerRef.current);
            timerRef.current = null;
        }
        composingRef.current = false;
        lastNavigationRef.current = currentHref;
        setQuery(serverQuery);
    }, [currentHref, serverQuery]);

    useEffect(() => {
        return () => {
            timerGenerationRef.current += 1;
            if (timerRef.current !== null) {
                window.clearTimeout(timerRef.current);
                timerRef.current = null;
            }
        };
    }, []);

    function searchHref(value: string): string {
        const q = value.trim();
        return feedHref({
            page: 1,
            ...(q ? { q } : {}),
            ...(state.tag ? { tag: state.tag } : {}),
        });
    }

    function cancelPendingSearch(): void {
        timerGenerationRef.current += 1;
        if (timerRef.current !== null) {
            window.clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    }

    function replaceSearch(value: string): void {
        const href = searchHref(value);
        if (href === lastNavigationRef.current) {
            return;
        }
        lastNavigationRef.current = href;
        router.replace(href);
    }

    function scheduleSearch(value: string): void {
        cancelPendingSearch();
        const href = searchHref(value);
        if (href === lastNavigationRef.current) {
            return;
        }
        const generation = timerGenerationRef.current;
        timerRef.current = window.setTimeout(() => {
            if (generation !== timerGenerationRef.current) {
                return;
            }
            timerRef.current = null;
            lastNavigationRef.current = href;
            router.replace(href);
        }, SEARCH_DEBOUNCE_MS);
    }

    function submitSearch(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (composingRef.current) {
            return;
        }
        cancelPendingSearch();
        replaceSearch(query);
    }

    return (
        <section className="feed-controls" aria-label="Search and filter posts">
            <form className="feed-search" onSubmit={submitSearch} role="search">
                <label className="sr-only" htmlFor="feed-search">
                    Search posts
                </label>
                <input
                    id="feed-search"
                    className="feed-search-input"
                    name="q"
                    type="search"
                    placeholder="Search posts"
                    value={query}
                    onChange={(event) => {
                        const value = event.currentTarget.value;
                        setQuery(value);
                        if (!composingRef.current) {
                            scheduleSearch(value);
                        }
                    }}
                    onCompositionEnd={(event) => {
                        composingRef.current = false;
                        const value = event.currentTarget.value;
                        setQuery(value);
                        scheduleSearch(value);
                    }}
                    onCompositionStart={() => {
                        composingRef.current = true;
                        cancelPendingSearch();
                    }}
                />
                <button
                    className="button-link button-link-primary"
                    type="submit"
                >
                    Search
                </button>
            </form>

            <nav className="feed-filter" aria-label="Filter posts by tag">
                <div className="feed-tag-list">
                    <a
                        className={`feed-tag ${state.tag ? "" : "feed-tag-active"}`}
                        aria-current={state.tag ? undefined : "page"}
                        href={feedHref({
                            page: 1,
                            ...(state.q ? { q: state.q } : {}),
                        })}
                    >
                        All
                    </a>
                    {tags.map((tag) => {
                        const active = state.tag === tag.slug;
                        return (
                            <a
                                key={tag.slug}
                                className={`feed-tag ${active ? "feed-tag-active" : ""}`}
                                aria-current={active ? "page" : undefined}
                                aria-label={`${tag.name} ${String(tag.count)} posts`}
                                href={feedHref({
                                    page: 1,
                                    ...(state.q ? { q: state.q } : {}),
                                    tag: tag.slug,
                                })}
                            >
                                <span aria-hidden="true">#{tag.name}</span>
                                <span
                                    className="feed-tag-count"
                                    aria-hidden="true"
                                >
                                    {tag.count}
                                </span>
                            </a>
                        );
                    })}
                </div>
            </nav>
        </section>
    );
}
