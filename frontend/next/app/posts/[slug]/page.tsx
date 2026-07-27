import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DateTime } from "@/components/date-time";
import { CommentsSection } from "@/components/comments-section";
import { PostBody } from "@/components/post-body";
import { PostReactions } from "@/components/post-reactions";
import { PreviewBanner } from "@/components/preview-banner";
import { Tags } from "@/components/tags";
import { SubscriptionForm } from "@/components/subscription-form";
import { postMetadata } from "@/lib/metadata";
import { loadPost } from "@/lib/server/post-loader";

type PostPageProps = {
    params: Promise<{ slug: string }>;
};

export async function generateMetadata({
    params,
}: PostPageProps): Promise<Metadata> {
    const loaded = await loadPost((await params).slug);
    if (loaded.status === "not-found") {
        return {
            title: "Post not found",
            robots: { index: false, follow: false },
        };
    }
    return postMetadata(loaded.post, loaded.preview);
}

export default async function PostPage({ params }: PostPageProps) {
    const loaded = await loadPost((await params).slug);
    if (loaded.status === "not-found") {
        notFound();
    }
    const { post, preview } = loaded;

    return (
        <article className="mx-auto max-w-3xl">
            {preview ? <PreviewBanner /> : null}

            <header className="border-b border-stone-200 pb-9">
                <p className="eyebrow">Post</p>
                <h1 className="mt-3 break-words text-balance text-4xl font-semibold tracking-tight text-stone-950 sm:text-5xl">
                    {post.title}
                </h1>
                <p className="mt-5 break-words text-xl leading-8 text-stone-600">
                    {post.excerpt}
                </p>
                <div className="mt-6 flex flex-wrap gap-x-4 gap-y-2 text-sm text-stone-500">
                    {post.published_at ? (
                        <DateTime
                            value={post.published_at}
                            label="Published "
                        />
                    ) : null}
                    {post.updated_at &&
                    post.updated_at !== post.published_at ? (
                        <DateTime value={post.updated_at} label="Updated " />
                    ) : null}
                </div>
                <div className="mt-5">
                    <Tags tags={post.tags} />
                </div>
            </header>

            <div className="mt-10">
                <PostBody blocks={post.body} />
            </div>

            {!preview ? (
                <>
                    <SubscriptionForm compact />
                    <PostReactions id={post.id} slug={post.slug} />
                    <CommentsSection slug={post.slug} />
                </>
            ) : null}
        </article>
    );
}
