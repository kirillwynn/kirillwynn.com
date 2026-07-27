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

function EmptyState({ title, children }: { title: string; children: string }) {
    return (
        <section
            className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center"
            aria-labelledby="empty-feed-title"
        >
            <h2
                id="empty-feed-title"
                className="text-xl font-semibold text-stone-950"
            >
                {title}
            </h2>
            <p className="mt-2 text-stone-600">{children}</p>
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
            <div className="mx-auto max-w-4xl">
                <EmptyState title="Invalid Feed URL">
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
        <div className="mx-auto max-w-4xl">
            <header className="mb-10 max-w-2xl">
                <p className="eyebrow">Personal publishing</p>
                <h1 className="mt-3 text-balance text-4xl font-semibold tracking-tight text-stone-950 sm:text-5xl">
                    Notes from building software and systems.
                </h1>
                <p className="mt-5 text-lg leading-8 text-stone-600">
                    Long-form writing by Kirill Wynn. Latest posts first.
                </p>
            </header>

            {!draft.isEnabled ? <SubscriptionForm /> : null}

            <FeedControls state={state} tags={tagResponse.results} />

            {unknownTag ? (
                <EmptyState title="Unknown tag">
                    This tag is not attached to any published post.
                </EmptyState>
            ) : feed.results.length === 0 && filtered ? (
                <EmptyState title="No posts found">
                    No published posts match the active search and tag filters.
                </EmptyState>
            ) : feed.results.length === 0 ? (
                <EmptyState title="No published posts yet">
                    New writing will appear here after it is published.
                </EmptyState>
            ) : (
                <div className="space-y-10">
                    {feed.results.map((post) => (
                        <PostCard key={post.id} post={post} />
                    ))}
                </div>
            )}

            {feed.count > 0 && feed.results.length > 0 ? (
                <Pagination
                    state={state}
                    hasPrevious={feed.previous !== null}
                    hasNext={feed.next !== null}
                />
            ) : null}
        </div>
    );
}
