import type { ContentTag } from "@/lib/content-contract";

export function Tags({
    tags,
    variant = "default",
}: {
    tags: ContentTag[];
    variant?: "default" | "feed";
}) {
    if (tags.length === 0) {
        return null;
    }

    if (variant === "feed") {
        return (
            <ul className="feed-entry-tags" aria-label="Tags">
                {tags.map((tag) => (
                    <li key={`${tag.slug}:${tag.name}`}>#{tag.name}</li>
                ))}
            </ul>
        );
    }

    return (
        <ul className="flex flex-wrap gap-2" aria-label="Tags">
            {tags.map((tag) => (
                <li
                    key={`${tag.slug}:${tag.name}`}
                    className="rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium text-stone-700"
                >
                    {tag.name}
                </li>
            ))}
        </ul>
    );
}
