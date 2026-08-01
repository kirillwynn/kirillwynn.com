import { ContentImage } from "@/components/content-image";
import { DateTime } from "@/components/date-time";
import { Tags } from "@/components/tags";
import type { PostListItem } from "@/lib/content-contract";
import { postPath } from "@/lib/slug";
import type { ReactNode } from "react";

export function PostCard({
    post,
    reactionContent,
}: {
    post: PostListItem;
    reactionContent?: ReactNode;
}) {
    const href = postPath(post.slug);
    if (!href) {
        return null;
    }

    return (
        <article className="feed-entry">
            <div className="feed-entry-meta">
                {post.display_published_at ? (
                    <DateTime value={post.display_published_at} />
                ) : null}
                <span>by {post.author.display_name}</span>
                <Tags tags={post.tags} variant="feed" />
            </div>
            <div className="feed-entry-layout">
                <div className="min-w-0">
                    <h2 className="feed-entry-title">
                        <a href={href}>{post.title}</a>
                    </h2>
                    <p className="feed-entry-excerpt">{post.excerpt}</p>
                    {reactionContent}
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
