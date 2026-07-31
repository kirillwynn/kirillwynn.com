import type { Metadata } from "next";

import type { PostDetail } from "@/lib/content-contract";

export function postMetadata(post: PostDetail, preview: boolean): Metadata {
    const image = post.open_graph.image?.renditions["1440w"];

    return {
        title: post.seo.title,
        description: post.seo.description,
        alternates: {
            canonical: post.canonical_url,
        },
        robots: preview
            ? {
                  index: false,
                  follow: false,
                  nocache: true,
              }
            : undefined,
        keywords: post.tags.map((tag) => tag.name),
        openGraph: {
            type: "article",
            url: post.canonical_url,
            title: post.open_graph.title,
            description: post.open_graph.description,
            publishedTime: post.display_published_at ?? undefined,
            modifiedTime: post.updated_at ?? undefined,
            tags: post.tags.map((tag) => tag.name),
            images:
                image && post.open_graph.image
                    ? [
                          {
                              url: image.url,
                              width: image.width,
                              height: image.height,
                              alt: post.open_graph.image.decorative
                                  ? ""
                                  : post.open_graph.image.alt,
                          },
                      ]
                    : undefined,
        },
    };
}
