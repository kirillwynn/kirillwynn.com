import type { ContentTag } from "@/lib/content-contract";

export function Tags({ tags }: { tags: ContentTag[] }) {
    if (tags.length === 0) {
        return null;
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
