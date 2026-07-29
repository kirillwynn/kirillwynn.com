import type { Metadata } from "next";
import { draftMode } from "next/headers";
import { notFound } from "next/navigation";

import { FeedControls } from "@/components/feed-controls";
import { Pagination } from "@/components/pagination";
import { PostCard } from "@/components/post-card";
import { SubscriptionForm } from "@/components/subscription-form";
import { parseFeedState } from "@/lib/feed-state";
import { getAvailableTags, getPublicPosts } from "@/lib/server/django";

type HomeSearchParams = Record<string, string | string[] | undefined>;

const FEED_METADATA = {
    title: "Feed",
    description: "The latest writing from Kirill Wynn.",
    alternates: { canonical: "/" },
    openGraph: {
        title: "Kirill Wynn — Feed",
        description: "The latest writing from Kirill Wynn.",
        url: "/",
    },
} satisfies Metadata;

export async function generateMetadata({
    searchParams,
}: {
    searchParams: Promise<HomeSearchParams>;
}): Promise<Metadata> {
    const parsed = parseFeedState(await searchParams);
    const variant =
        !parsed.valid ||
        parsed.state.page > 1 ||
        Boolean(parsed.state.q || parsed.state.tag);
    return {
        ...FEED_METADATA,
        ...(variant ? { robots: { index: false, follow: true } } : {}),
    };
}

function EmptyState({
    title,
    children,
    actionHref,
    actionLabel,
    headingLevel = "h2",
}: {
    title: string;
    children: string;
    actionHref?: string;
    actionLabel?: string;
    headingLevel?: "h1" | "h2";
}) {
    const Heading = headingLevel;

    return (
        <section
            className="state-panel feed-empty"
            aria-labelledby="empty-feed-title"
        >
            <Heading id="empty-feed-title">{title}</Heading>
            <p>{children}</p>
            {actionHref && actionLabel ? (
                <a className="button-link" href={actionHref}>
                    {actionLabel}
                </a>
            ) : null}
        </section>
    );
}

export default async function HomePage({
    searchParams,
}: {
    searchParams: Promise<HomeSearchParams>;
}) {
    const parsed = parseFeedState(await searchParams);
    if (!parsed.valid) {
        return (
            <div className="state-page">
                <EmptyState
                    title="Invalid Feed URL"
                    actionHref="/"
                    actionLabel="Return to Feed"
                    headingLevel="h1"
                >
                    Check the search, tag, and page parameters and try again.
                </EmptyState>
            </div>
        );
    }

    const state = parsed.state;
    const [feed, tagResponse, draft] = await Promise.all([
        getPublicPosts(state),
        getAvailableTags(),
        draftMode(),
    ]);
    if (!feed) {
        notFound();
    }

    const unknownTag =
        state.tag !== undefined &&
        !tagResponse.results.some((tag) => tag.slug === state.tag);
    const filtered = Boolean(state.q || state.tag);

    return (
        <div className="page-shell">
            <header className="feed-header">
                <h1 className="feed-title">Feed</h1>
            </header>

            <FeedControls state={state} tags={tagResponse.results} />

            {unknownTag ? (
                <EmptyState
                    title="Unknown tag"
                    actionHref="/"
                    actionLabel="View all posts"
                >
                    This tag is not attached to any published post.
                </EmptyState>
            ) : feed.results.length === 0 && filtered ? (
                <EmptyState
                    title="No posts found"
                    actionHref="/"
                    actionLabel="Clear filters"
                >
                    No published posts match the active search and tag filters.
                </EmptyState>
            ) : feed.results.length === 0 ? (
                <EmptyState title="No published posts yet">
                    New writing will appear here after it is published.
                </EmptyState>
            ) : (
                <section className="feed-stream" aria-label="Latest posts">
                    {feed.results.map((post) => (
                        <PostCard key={post.id} post={post} />
                    ))}
                </section>
            )}

            {feed.results.length > 0 &&
            (feed.previous !== null || feed.next !== null) ? (
                <Pagination
                    state={state}
                    hasPrevious={feed.previous !== null}
                    hasNext={feed.next !== null}
                />
            ) : null}

            {!draft.isEnabled ? <SubscriptionForm /> : null}
        </div>
    );
}
