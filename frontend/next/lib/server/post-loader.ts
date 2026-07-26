import "server-only";

import { cache } from "react";
import { cookies, draftMode } from "next/headers";

import type { PostDetail } from "@/lib/content-contract";
import {
    getPublicPost,
    PreviewUnavailableError,
    resolvePreview,
} from "@/lib/server/django";
import { PREVIEW_SNAPSHOT_COOKIE } from "@/lib/server/preview-cookies";
import { decodeRouteSlug } from "@/lib/slug";

export type LoadedPost =
    | { status: "found"; post: PostDetail; preview: boolean }
    | { status: "not-found" };

export const loadPost = cache(
    async (routeSlug: string): Promise<LoadedPost> => {
        const slug = decodeRouteSlug(routeSlug);
        if (!slug) {
            return { status: "not-found" };
        }

        const draft = await draftMode();
        let post: PostDetail | null;
        if (draft.isEnabled) {
            const cookieStore = await cookies();
            const credential = cookieStore.get(PREVIEW_SNAPSHOT_COOKIE)?.value;
            if (!credential) {
                return { status: "not-found" };
            }
            try {
                post = await resolvePreview(credential);
            } catch (error) {
                if (error instanceof PreviewUnavailableError) {
                    return { status: "not-found" };
                }
                throw error;
            }
        } else {
            post = await getPublicPost(slug);
        }

        if (!post || post.slug !== slug) {
            return { status: "not-found" };
        }
        return { status: "found", post, preview: draft.isEnabled };
    },
);
