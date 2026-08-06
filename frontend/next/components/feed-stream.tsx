"use client";

import {
    type InfiniteData,
    useInfiniteQuery,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import {
    useCallback,
    useEffect,
    useLayoutEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { useAuth } from "@/components/auth-provider";
import { FeedControls } from "@/components/feed-controls";
import { PostCard } from "@/components/post-card";
import { ReactionBar } from "@/components/reaction-bar";
import type { PostListItem, PostListResponse } from "@/lib/content-contract";
import {
    feedApiPath,
    fetchFeedPage,
    PUBLIC_URL_CHANGE_EVENT,
    queryFromLocation,
} from "@/lib/feed-browser";
import { feedHref } from "@/lib/feed-state";
import {
    saveFeedScroll,
    scheduleFeedScrollRestoration,
} from "@/lib/feed-scroll-cache";
import { queryKeys } from "@/lib/query-keys";
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
    const { identityKey } = useAuth();
    const queryClient = useQueryClient();
    const reactionQuery = useQuery({
        enabled: false,
        initialData: initialReactions,
        queryKey: queryKeys.postReactions(identityKey, post.id),
        queryFn: () => Promise.resolve(initialReactions),
    });
    const reactions = reactionQuery.data;
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

    if (!target || reactions.length === 0) {
        return null;
    }

    function applyChange(change: ReactionChange): void {
        queryClient.setQueryData(
            queryKeys.postReactions(identityKey, post.id),
            change.reactions,
        );
    }

    return (
        <div className="feed-entry-reactions">
            <ReactionBar
                hidePicker
                initialReactions={reactions}
                onChange={applyChange}
                target={target}
            />
        </div>
    );
}

function FeedPage({
    loadReactions,
    posts,
}: {
    loadReactions: boolean;
    posts: PostListItem[];
}) {
    const { identityKey, status: authStatus } = useAuth();
    const postIds = useMemo(() => posts.map((post) => post.id), [posts]);
    const reactions = useQuery({
        enabled: loadReactions && authStatus === "ready" && postIds.length > 0,
        queryKey: queryKeys.feedReactionBatch(identityKey, postIds),
        queryFn: ({ signal }) => getPostReactionBatch(postIds, signal),
    });
    const reactionsByPost = useMemo(
        () =>
            Object.fromEntries(
                (reactions.data ?? []).map((result) => [
                    result.post_id,
                    result.reactions,
                ]),
            ) as Partial<Record<number, ReactionGroup[]>>,
        [reactions.data],
    );

    return (
        <>
            {posts.map((post) => {
                const postReactions = reactionsByPost[post.id];
                return (
                    <PostCard
                        key={post.id}
                        post={post}
                        reactionContent={
                            postReactions !== undefined ? (
                                <FeedReactionPills
                                    initialReactions={postReactions}
                                    post={post}
                                />
                            ) : null
                        }
                    />
                );
            })}
        </>
    );
}

function useAutomaticFeedLoading(
    enabled: boolean,
    load: () => void,
): { manual: boolean; sentinelRef: (node: HTMLDivElement | null) => void } {
    const [sentinel, setSentinel] = useState<HTMLDivElement | null>(null);
    const [manual, setManual] = useState(true);

    useEffect(() => {
        const saveData = Boolean(
            (
                navigator as Navigator & {
                    connection?: { saveData?: boolean };
                }
            ).connection?.saveData,
        );
        const reducedMotion = window.matchMedia(
            "(prefers-reduced-motion: reduce)",
        ).matches;
        setManual(
            typeof window.IntersectionObserver !== "function" ||
                saveData ||
                reducedMotion,
        );
    }, []);

    useEffect(() => {
        if (!enabled || manual || !sentinel) {
            return;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                if (entries.some((entry) => entry.isIntersecting)) {
                    load();
                }
            },
            { rootMargin: "480px 0px" },
        );
        observer.observe(sentinel);
        return () => {
            observer.disconnect();
        };
    }, [enabled, load, manual, sentinel]);

    return { manual, sentinelRef: setSentinel };
}

function uniquePagePosts(pages: PostListResponse[]): PostListItem[][] {
    const seen = new Set<number>();
    return pages.map((page) =>
        page.results.filter((post) => {
            if (seen.has(post.id)) {
                return false;
            }
            seen.add(post.id);
            return true;
        }),
    );
}

export function FeedStream({
    initialFeed,
    initialQuery,
    loadReactions,
}: {
    initialFeed: PostListResponse;
    initialQuery: string;
    loadReactions: boolean;
}) {
    const pathname = usePathname();
    const leavingFeedRef = useRef(false);
    const nextRequestRef = useRef(false);
    const [query, setQuery] = useState(initialQuery);
    const [manualAfterError, setManualAfterError] = useState(false);
    const initialPath = feedApiPath(initialQuery);
    const feed = useInfiniteQuery<
        PostListResponse,
        Error,
        InfiniteData<PostListResponse, string>,
        ReturnType<typeof queryKeys.feed>,
        string
    >({
        queryKey: queryKeys.feed(query),
        initialPageParam: feedApiPath(query),
        initialData:
            query === initialQuery
                ? { pages: [initialFeed], pageParams: [initialPath] }
                : undefined,
        queryFn: ({ pageParam, signal }) =>
            fetchFeedPage(pageParam, query, signal),
        getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    });
    const currentData = feed.data as
        | InfiniteData<PostListResponse, string>
        | undefined;
    const pages = currentData?.pages ?? [];
    const pagePosts = useMemo(() => uniquePagePosts(pages), [pages]);
    const postCount = pagePosts.reduce(
        (total, posts) => total + posts.length,
        0,
    );
    const hasNextPage = feed.hasNextPage;
    const loadNext = useCallback(() => {
        if (!hasNextPage || feed.isFetchingNextPage || nextRequestRef.current) {
            return;
        }
        nextRequestRef.current = true;
        void feed.fetchNextPage({ cancelRefetch: false }).finally(() => {
            nextRequestRef.current = false;
        });
    }, [feed, hasNextPage]);
    const autoLoad = useAutomaticFeedLoading(
        hasNextPage &&
            !feed.isFetchingNextPage &&
            !feed.isFetchNextPageError &&
            !manualAfterError,
        loadNext,
    );

    useEffect(() => {
        if (feed.isFetchNextPageError) {
            setManualAfterError(true);
        }
    }, [feed.isFetchNextPageError]);

    useEffect(() => {
        setManualAfterError(false);
    }, [query]);

    useLayoutEffect(() => {
        if (pathname !== "/" || window.location.pathname !== "/") {
            return;
        }
        const locationQuery = queryFromLocation(window.location);
        if (locationQuery !== query) {
            setQuery(locationQuery);
            return;
        }
        leavingFeedRef.current = false;
        scheduleFeedScrollRestoration(query);
    }, [pathname, query]);

    useEffect(() => {
        if (pathname !== "/") {
            return;
        }
        const save = () => {
            if (leavingFeedRef.current || window.location.pathname !== "/") {
                return;
            }
            saveFeedScroll(query, window.scrollY);
        };
        const saveBeforeNavigation = (event: MouseEvent) => {
            const target = event.target;
            const anchor =
                target instanceof Element
                    ? target.closest<HTMLAnchorElement>("a[href]")
                    : null;
            if (!anchor) {
                return;
            }
            const destination = new URL(anchor.href, window.location.href);
            if (
                destination.origin === window.location.origin &&
                (destination.pathname !== "/" || destination.search !== "")
            ) {
                saveFeedScroll(query, window.scrollY);
                leavingFeedRef.current = true;
            }
        };
        window.addEventListener("scroll", save, { passive: true });
        document.addEventListener("click", saveBeforeNavigation, true);
        return () => {
            save();
            window.removeEventListener("scroll", save);
            document.removeEventListener("click", saveBeforeNavigation, true);
        };
    }, [pathname, query]);

    useEffect(() => {
        const restore = () => {
            setQuery(queryFromLocation(window.location));
        };
        window.addEventListener("popstate", restore);
        return () => {
            window.removeEventListener("popstate", restore);
        };
    }, []);

    function search(nextQuery: string): void {
        if (nextQuery === query) {
            return;
        }
        saveFeedScroll(query, window.scrollY);
        const href = feedHref({
            page: 1,
            ...(nextQuery ? { q: nextQuery } : {}),
        });
        window.history.pushState(null, "", href);
        window.dispatchEvent(new Event(PUBLIC_URL_CHANGE_EVENT));
        setQuery(nextQuery);
        window.scrollTo({ top: 0 });
    }

    return (
        <>
            <FeedControls
                onSearch={search}
                query={query}
                searching={feed.isFetching && !feed.isFetchingNextPage}
            />

            {pages.length === 0 &&
            feed.fetchStatus === "fetching" ? null : feed.isError &&
              !feed.isFetchNextPageError ? (
                <section className="state-panel feed-empty" role="status">
                    <h2>The content service did not respond.</h2>
                    <p>
                        This is a temporary upstream problem. Please try again.
                    </p>
                    <button
                        className="button-link button-link-primary"
                        onClick={() => void feed.refetch()}
                        type="button"
                    >
                        Try again
                    </button>
                </section>
            ) : postCount === 0 && query ? (
                <section className="state-panel feed-empty">
                    <h2>No posts found</h2>
                    <p>No published posts match this search.</p>
                </section>
            ) : postCount === 0 ? (
                <section className="state-panel feed-empty">
                    <h2>No published posts yet</h2>
                    <p>New writing will appear here after it is published.</p>
                </section>
            ) : (
                <section className="feed-stream" aria-label="Latest posts">
                    {pagePosts.map((posts, index) => (
                        <FeedPage
                            key={currentData?.pageParams[index] ?? index}
                            loadReactions={loadReactions}
                            posts={posts}
                        />
                    ))}
                </section>
            )}

            {postCount > 0 && hasNextPage ? (
                <div className="feed-load-more">
                    <div
                        aria-hidden="true"
                        className="feed-sentinel"
                        ref={autoLoad.sentinelRef}
                    />
                    {autoLoad.manual ||
                    manualAfterError ||
                    feed.isFetchNextPageError ? (
                        <button
                            aria-disabled={feed.isFetchingNextPage}
                            className="button-link"
                            onClick={loadNext}
                            type="button"
                        >
                            {feed.isFetchingNextPage
                                ? "Loading older posts…"
                                : feed.isFetchNextPageError
                                  ? "Try loading older posts again"
                                  : "Load older posts"}
                        </button>
                    ) : feed.isFetchingNextPage ? (
                        <p role="status">Loading older posts…</p>
                    ) : null}
                </div>
            ) : postCount > 0 ? (
                <p className="feed-archive-beginning">
                    Beginning of the archive
                </p>
            ) : null}
        </>
    );
}
