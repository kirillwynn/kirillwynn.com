import "server-only";

import type { PostDetail } from "@/lib/content-contract";
import { djangoApiUrl } from "@/lib/server/config";

export async function resolvePreview(credential: string): Promise<PostDetail> {
    const response = await fetch(`${djangoApiUrl()}/api/v1/preview/resolve/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential }),
        cache: "no-store",
    });
    if (!response.ok) {
        throw new Error("Preview is unavailable");
    }
    return (await response.json()) as PostDetail;
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
        throw new Error("Public content API request failed");
    }
    return (await response.json()) as PostDetail;
}
