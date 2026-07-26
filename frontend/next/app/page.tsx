import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Pagination } from "@/components/pagination";
import { PostCard } from "@/components/post-card";
import { parsePageParam } from "@/lib/pagination";
import { getPublicPosts } from "@/lib/server/django";

export const metadata: Metadata = {
    title: "Feed",
    description: "The latest writing from Kirill Wynn.",
    alternates: { canonical: "/" },
    openGraph: {
        title: "Kirill Wynn — Feed",
        description: "The latest writing from Kirill Wynn.",
        url: "/",
    },
};

export default async function HomePage({
    searchParams,
}: {
    searchParams: Promise<{ page?: string | string[] }>;
}) {
    const page = parsePageParam((await searchParams).page);
    if (!page) {
        notFound();
    }
    const feed = await getPublicPosts(page);
    if (!feed || (page > 1 && feed.results.length === 0)) {
        notFound();
    }

    return (
        <div className="mx-auto max-w-4xl">
            <header className="mb-12 max-w-2xl">
                <p className="eyebrow">Personal publishing</p>
                <h1 className="mt-3 text-balance text-4xl font-semibold tracking-tight text-stone-950 sm:text-5xl">
                    Notes from building software and systems.
                </h1>
                <p className="mt-5 text-lg leading-8 text-stone-600">
                    Long-form writing by Kirill Wynn. Latest posts first.
                </p>
            </header>

            {feed.results.length === 0 ? (
                <section
                    className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center"
                    aria-labelledby="empty-feed-title"
                >
                    <h2
                        id="empty-feed-title"
                        className="text-xl font-semibold text-stone-950"
                    >
                        No published posts yet
                    </h2>
                    <p className="mt-2 text-stone-600">
                        New writing will appear here after it is published.
                    </p>
                </section>
            ) : (
                <div className="space-y-10">
                    {feed.results.map((post) => (
                        <PostCard key={post.id} post={post} />
                    ))}
                </div>
            )}

            {feed.count > 0 ? (
                <Pagination
                    page={page}
                    hasPrevious={feed.previous !== null}
                    hasNext={feed.next !== null}
                />
            ) : null}
        </div>
    );
}
