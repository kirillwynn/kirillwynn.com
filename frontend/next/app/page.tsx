import type { Metadata } from "next";
import Link from "next/link";
import { draftMode } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { Suspense } from "react";

import { FeedStream } from "@/components/feed-stream";
import { feedHref, parseFeedState } from "@/lib/feed-state";
import { getPublicPosts } from "@/lib/server/django";

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
    const variant = !parsed.valid || Boolean(parsed.state.q);
    return {
        ...FEED_METADATA,
        ...(variant ? { robots: { index: false, follow: true } } : {}),
    };
}

function legacyFeedHref(parameters: HomeSearchParams): string | null {
    if (!("tag" in parameters) && !("page" in parameters)) {
        return null;
    }
    const parsed = parseFeedState({ q: parameters.q });
    return feedHref({
        page: 1,
        ...(parsed.valid && parsed.state.q ? { q: parsed.state.q } : {}),
    });
}

function InvalidFeedUrl() {
    return (
        <div className="state-page">
            <section
                className="state-panel feed-empty"
                aria-labelledby="empty-feed-title"
            >
                <h1 id="empty-feed-title">Invalid Feed URL</h1>
                <p>Check the search parameter and try again.</p>
                <Link className="button-link" href="/">
                    Return to Feed
                </Link>
            </section>
        </div>
    );
}

export async function FeedPage({
    searchParams,
}: {
    searchParams: Promise<HomeSearchParams>;
}) {
    const parameters = await searchParams;
    const legacyHref = legacyFeedHref(parameters);
    if (legacyHref !== null) {
        redirect(legacyHref);
    }

    const parsed = parseFeedState(parameters);
    if (!parsed.valid || parsed.state.tag || parsed.state.page !== 1) {
        return <InvalidFeedUrl />;
    }

    const state = parsed.state;
    const [feed, draft] = await Promise.all([
        getPublicPosts(state),
        draftMode(),
    ]);
    if (!feed) {
        notFound();
    }

    return (
        <div className="page-shell">
            <h1 className="sr-only">Feed</h1>
            <FeedStream
                initialFeed={feed}
                initialQuery={state.q ?? ""}
                loadReactions={!draft.isEnabled}
            />
        </div>
    );
}

export default function HomePage({
    searchParams,
}: {
    searchParams: Promise<HomeSearchParams>;
}) {
    return (
        <Suspense
            fallback={
                <div className="page-shell">
                    <h1 className="sr-only">Feed</h1>
                </div>
            }
        >
            <FeedPage searchParams={searchParams} />
        </Suspense>
    );
}
