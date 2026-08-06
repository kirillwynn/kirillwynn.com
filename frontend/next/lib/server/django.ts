import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import type {
    AvailableTagResponse,
    PostDetail,
    PostListResponse,
} from "@/lib/content-contract";
import { checkedNextFeedPath } from "@/lib/feed-browser";
import { feedHref, type FeedState } from "@/lib/feed-state";
import { djangoApiUrl, publicSiteUrl } from "@/lib/server/config";

export class ContentApiError extends Error {
    constructor(message = "Public content API request failed") {
        super(message);
        this.name = "ContentApiError";
    }
}

export class PreviewUnavailableError extends Error {
    constructor() {
        super("Preview is unavailable");
        this.name = "PreviewUnavailableError";
    }
}

function assertPositivePage(page: number): void {
    if (!Number.isSafeInteger(page) || page < 1) {
        throw new TypeError("page must be a positive integer");
    }
}

function upstreamHeaders(extra: Record<string, string> = {}): HeadersInit {
    const publicOrigin = new URL(publicSiteUrl());
    return {
        Host: publicOrigin.host,
        "X-Forwarded-Proto": publicOrigin.protocol.slice(0, -1),
        ...extra,
    };
}

export async function resolvePreview(credential: string): Promise<PostDetail> {
    const response = await fetch(`${djangoApiUrl()}/api/v1/preview/resolve/`, {
        method: "POST",
        headers: upstreamHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ credential }),
        cache: "no-store",
    });
    if (response.status === 404) {
        throw new PreviewUnavailableError();
    }
    if (!response.ok) {
        throw new ContentApiError("Preview API request failed");
    }
    return (await response.json()) as PostDetail;
}

export async function getPublicPosts(
    state: FeedState,
): Promise<PostListResponse | null> {
    "use cache";
    cacheLife({ stale: 30, revalidate: 60, expire: 86_400 });
    cacheTag("posts");
    assertPositivePage(state.page);
    const query = feedHref(state).slice(2);
    const suffix = query ? `?${query}` : "";
    const response = await fetch(`${djangoApiUrl()}/api/v1/posts/${suffix}`, {
        headers: upstreamHeaders(),
        next: { tags: ["posts"] },
    });
    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        throw new ContentApiError();
    }
    const page = (await response.json()) as PostListResponse;
    return {
        ...page,
        next: checkedNextFeedPath(
            page.next,
            state.q ?? "",
            publicSiteUrl(),
            state.tag,
        ),
    };
}

export async function getAvailableTags(): Promise<AvailableTagResponse> {
    "use cache";
    cacheLife({ stale: 30, revalidate: 60, expire: 86_400 });
    cacheTag("posts");
    const response = await fetch(`${djangoApiUrl()}/api/v1/tags/`, {
        headers: upstreamHeaders(),
        next: { tags: ["posts"] },
    });
    if (!response.ok) {
        throw new ContentApiError("Public tag API request failed");
    }
    return (await response.json()) as AvailableTagResponse;
}

export async function getPublicPost(slug: string): Promise<PostDetail | null> {
    "use cache";
    cacheLife({ stale: 30, revalidate: 60, expire: 86_400 });
    cacheTag("posts", `post-slug:${slug}`);
    const response = await fetch(
        `${djangoApiUrl()}/api/v1/posts/${encodeURIComponent(slug)}/`,
        {
            headers: upstreamHeaders(),
            next: { tags: [`post-slug:${slug}`] },
        },
    );
    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        throw new ContentApiError();
    }
    const post = (await response.json()) as PostDetail;
    cacheTag(`post:${String(post.id)}`);
    return post;
}
