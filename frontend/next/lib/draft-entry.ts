import type { PostDetail } from "@/lib/content-contract";

export type DraftEntryResult =
    | { ok: true; path: string; credential: string }
    | { ok: false };

export function verifiedPreviewPath(post: PostDetail): string | null {
    const expected = `/posts/${post.slug}`;
    return post.canonical_path === expected ? expected : null;
}

export async function enterDraftMode(
    credential: string | undefined,
    resolve: (value: string) => Promise<PostDetail>,
    enable: () => void | Promise<void>,
): Promise<DraftEntryResult> {
    if (!credential) {
        return { ok: false };
    }
    try {
        const post = await resolve(credential);
        const path = verifiedPreviewPath(post);
        if (!path) {
            return { ok: false };
        }
        await enable();
        return { ok: true, path, credential };
    } catch {
        return { ok: false };
    }
}
