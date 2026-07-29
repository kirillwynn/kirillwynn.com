"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { AvailableTag } from "@/lib/content-contract";
import { feedHref, type FeedState } from "@/lib/feed-state";

export function FeedControls({
    state,
    tags,
}: {
    state: FeedState;
    tags: AvailableTag[];
}) {
    const router = useRouter();
    const [query, setQuery] = useState(state.q ?? "");

    useEffect(() => {
        setQuery(state.q ?? "");
    }, [state.q]);

    function submitSearch(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const q = query.trim();
        router.push(
            feedHref({
                page: 1,
                ...(q ? { q } : {}),
                ...(state.tag ? { tag: state.tag } : {}),
            }),
        );
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
                        setQuery(event.currentTarget.value);
                    }}
                />
                <button
                    className="button-link button-link-primary"
                    type="submit"
                >
                    Search
                </button>
                {state.q ? (
                    <a
                        className="feed-clear"
                        href={feedHref({
                            page: 1,
                            ...(state.tag ? { tag: state.tag } : {}),
                        })}
                    >
                        Clear search
                    </a>
                ) : null}
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
                {state.tag ? (
                    <a
                        className="feed-clear"
                        href={feedHref({
                            page: 1,
                            ...(state.q ? { q: state.q } : {}),
                        })}
                    >
                        Clear tag
                    </a>
                ) : null}
            </nav>
        </section>
    );
}
