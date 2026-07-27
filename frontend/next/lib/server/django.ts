import "server-only";

import type {
    AvailableTagResponse,
    PostDetail,
    PostListResponse,
} from "@/lib/content-contract";
import { feedHref, type FeedState } from "@/lib/feed-state";
import { djangoApiUrl } from "@/lib/server/config";

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

export async function resolvePreview(credential: string): Promise<PostDetail> {
    const response = await fetch(`${djangoApiUrl()}/api/v1/preview/resolve/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
    assertPositivePage(state.page);
    const query = feedHref(state).slice(2);
    const suffix = query ? `?${query}` : "";
    const response = await fetch(`${djangoApiUrl()}/api/v1/posts/${suffix}`, {
        next: { tags: ["posts"] },
    });
    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        throw new ContentApiError();
    }
    return (await response.json()) as PostListResponse;
}

export async function getAvailableTags(): Promise<AvailableTagResponse> {
    const response = await fetch(`${djangoApiUrl()}/api/v1/tags/`, {
        next: { tags: ["posts"] },
    });
    if (!response.ok) {
        throw new ContentApiError("Public tag API request failed");
    }
    return (await response.json()) as AvailableTagResponse;
}

export async function getPublicPost(slug: string): Promise<PostDetail | null> {
    const response = await fetch(
        `${djangoApiUrl()}/api/v1/posts/${encodeURIComponent(slug)}/`,
        {
            next: { tags: [`post-slug:${slug}`] },
        },
    );
    if (response.status === 404) {
        return null;
    }
    if (!response.ok) {
        throw new ContentApiError();
    }
    return (await response.json()) as PostDetail;
}
