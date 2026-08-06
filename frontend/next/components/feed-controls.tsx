"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";

const SEARCH_DEBOUNCE_MS = 275;

export function FeedControls({
    searching,
    query,
    onSearch,
}: {
    searching: boolean;
    query: string;
    onSearch: (query: string) => void;
}) {
    const [value, setValue] = useState(query);
    const [showSearching, setShowSearching] = useState(false);
    const timerRef = useRef<number | null>(null);
    const composingRef = useRef(false);

    useEffect(() => {
        setValue(query);
    }, [query]);

    useEffect(() => {
        if (!searching) {
            setShowSearching(false);
            return;
        }
        const timer = window.setTimeout(() => {
            setShowSearching(true);
        }, 150);
        return () => {
            window.clearTimeout(timer);
        };
    }, [searching]);

    useEffect(
        () => () => {
            if (timerRef.current !== null) {
                window.clearTimeout(timerRef.current);
            }
        },
        [],
    );

    function cancelPendingSearch(): void {
        if (timerRef.current !== null) {
            window.clearTimeout(timerRef.current);
            timerRef.current = null;
        }
    }

    function scheduleSearch(nextValue: string): void {
        cancelPendingSearch();
        timerRef.current = window.setTimeout(() => {
            timerRef.current = null;
            onSearch(nextValue.trim());
        }, SEARCH_DEBOUNCE_MS);
    }

    function submit(event: FormEvent<HTMLFormElement>): void {
        event.preventDefault();
        if (composingRef.current) {
            return;
        }
        cancelPendingSearch();
        onSearch(value.trim());
    }

    return (
        <section className="feed-controls" aria-label="Search posts">
            <div className="feed-controls-row">
                <form className="feed-search" onSubmit={submit} role="search">
                    <label className="sr-only" htmlFor="feed-search">
                        Search posts
                    </label>
                    <input
                        id="feed-search"
                        className="feed-search-input"
                        maxLength={200}
                        name="q"
                        type="search"
                        placeholder="Search posts"
                        value={value}
                        onChange={(event) => {
                            const nextValue = event.currentTarget.value;
                            setValue(nextValue);
                            if (!composingRef.current) {
                                scheduleSearch(nextValue);
                            }
                        }}
                        onCompositionEnd={(event) => {
                            composingRef.current = false;
                            const nextValue = event.currentTarget.value;
                            setValue(nextValue);
                            scheduleSearch(nextValue);
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
                <Link
                    className="feed-subscribe-link"
                    href="/subscriptions/"
                    prefetch={false}
                >
                    Subscribe
                </Link>
            </div>
            {showSearching ? (
                <p className="feed-search-status" role="status">
                    Searching…
                </p>
            ) : null}
        </section>
    );
}
