import { cookies, draftMode } from "next/headers";
import { notFound } from "next/navigation";

import { getPublicPost, resolvePreview } from "@/lib/server/django";
import { PREVIEW_SNAPSHOT_COOKIE } from "@/lib/server/preview-cookies";
import { decodeRouteSlug } from "@/lib/slug";

export default async function DiagnosticPostPage({
    params,
}: {
    params: Promise<{ slug: string }>;
}) {
    const { slug: encodedSlug } = await params;
    const slug = decodeRouteSlug(encodedSlug);
    if (!slug) {
        notFound();
    }
    const draft = await draftMode();
    const cookieStore = await cookies();

    let post;
    if (draft.isEnabled) {
        const credential = cookieStore.get(PREVIEW_SNAPSHOT_COOKIE)?.value;
        if (!credential) {
            notFound();
        }
        post = await resolvePreview(credential);
    } else {
        post = await getPublicPost(slug);
    }

    if (!post || post.slug !== slug) {
        notFound();
    }

    return (
        <main>
            <p>
                <strong>
                    {draft.isEnabled ? "Draft snapshot" : "Public API"}
                </strong>
            </p>
            <h1>{post.title}</h1>
            <p>{post.excerpt}</p>
            <p>
                Page ID {post.id}; contract {post.api_version};{" "}
                {post.body.length} body blocks.
            </p>
            <pre>{JSON.stringify(post.body, null, 2)}</pre>
            {draft.isEnabled ? (
                <p>
                    <a href="/api/draft/disable">Exit Draft Mode</a>
                </p>
            ) : null}
        </main>
    );
}
