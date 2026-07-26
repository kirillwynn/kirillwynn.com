import { ContentImage } from "@/components/content-image";
import { DateTime } from "@/components/date-time";
import { Tags } from "@/components/tags";
import type { PostListItem } from "@/lib/content-contract";
import { postPath } from "@/lib/slug";

export function PostCard({ post }: { post: PostListItem }) {
    const href = postPath(post.slug);
    if (!href) {
        return null;
    }

    return (
        <article className="grid gap-5 border-b border-stone-200 pb-10 last:border-0 md:grid-cols-[minmax(0,1fr)_13rem]">
            <div className="min-w-0">
                {post.published_at ? (
                    <p className="mb-3 text-sm text-stone-500">
                        <DateTime value={post.published_at} />
                    </p>
                ) : null}
                <h2 className="text-balance text-2xl font-semibold tracking-tight text-stone-950 sm:text-3xl">
                    <a
                        href={href}
                        className="rounded-sm decoration-2 underline-offset-4 hover:underline"
                    >
                        {post.title}
                    </a>
                </h2>
                <p className="mt-3 break-words text-base leading-7 text-stone-700">
                    {post.excerpt}
                </p>
                <div className="mt-5">
                    <Tags tags={post.tags} />
                </div>
            </div>
            {post.lead_image ? (
                <a
                    href={href}
                    aria-label={`Read ${post.title}`}
                    className="order-first overflow-hidden rounded-xl bg-stone-100 md:order-last"
                >
                    <ContentImage
                        image={post.lead_image}
                        className="aspect-[16/10] h-full w-full object-cover"
                        sizes="(min-width: 48rem) 13rem, calc(100vw - 2rem)"
                    />
                </a>
            ) : null}
        </article>
    );
}
