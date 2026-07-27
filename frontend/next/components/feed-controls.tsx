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
        <section
            className="mb-10 rounded-2xl border border-stone-200 bg-white p-5 sm:p-6"
            aria-label="Search and filter posts"
        >
            <form onSubmit={submitSearch} role="search">
                <label
                    className="block text-sm font-semibold text-stone-900"
                    htmlFor="feed-search"
                >
                    Search posts
                </label>
                <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                    <input
                        id="feed-search"
                        className="feed-search-input"
                        name="q"
                        type="search"
                        value={query}
                        onChange={(event) => {
                            setQuery(event.currentTarget.value);
                        }}
                    />
                    <button className="button-link" type="submit">
                        Search
                    </button>
                    {state.q ? (
                        <a
                            className="button-link"
                            href={feedHref({
                                page: 1,
                                ...(state.tag ? { tag: state.tag } : {}),
                            })}
                        >
                            Clear search
                        </a>
                    ) : null}
                </div>
            </form>

            <nav className="mt-6" aria-label="Filter posts by tag">
                <p className="text-sm font-semibold text-stone-900">Tags</p>
                <div className="mt-2 flex flex-wrap gap-2">
                    <a
                        className={`feed-tag ${state.tag ? "" : "feed-tag-active"}`}
                        aria-current={state.tag ? undefined : "page"}
                        href={feedHref({
                            page: 1,
                            ...(state.q ? { q: state.q } : {}),
                        })}
                    >
                        All posts
                    </a>
                    {tags.map((tag) => {
                        const active = state.tag === tag.slug;
                        return (
                            <a
                                key={tag.slug}
                                className={`feed-tag ${active ? "feed-tag-active" : ""}`}
                                aria-current={active ? "page" : undefined}
                                href={feedHref({
                                    page: 1,
                                    ...(state.q ? { q: state.q } : {}),
                                    tag: tag.slug,
                                })}
                            >
                                {tag.name}{" "}
                                <span aria-label={`${String(tag.count)} posts`}>
                                    ({tag.count})
                                </span>
                            </a>
                        );
                    })}
                </div>
                {state.tag ? (
                    <a
                        className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-amber-800 underline underline-offset-4"
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
