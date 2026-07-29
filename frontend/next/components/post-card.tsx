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
        <article className="feed-entry">
            {post.published_at || post.tags.length > 0 ? (
                <div className="feed-entry-meta">
                    {post.published_at ? (
                        <DateTime value={post.published_at} />
                    ) : null}
                    <Tags tags={post.tags} variant="feed" />
                </div>
            ) : null}
            <div className="feed-entry-layout">
                <div className="min-w-0">
                    <h2 className="feed-entry-title">
                        <a href={href}>{post.title}</a>
                    </h2>
                    <p className="feed-entry-excerpt">{post.excerpt}</p>
                </div>
                {post.lead_image ? (
                    <a
                        href={href}
                        aria-label={`Read ${post.title}`}
                        className="feed-entry-image"
                    >
                        <ContentImage
                            image={post.lead_image}
                            sizes="(min-width: 40rem) 7.5rem, 5.25rem"
                        />
                    </a>
                ) : null}
            </div>
        </article>
    );
}
