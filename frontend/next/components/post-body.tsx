import type { ReactNode } from "react";

import { ContentImage } from "@/components/content-image";
import type {
    ContentBlock,
    ContentImage as ContentImageData,
} from "@/lib/content-contract";
import { highlightCode } from "@/lib/code-highlighting";

function assertNever(value: never): never {
    throw new Error(`Unhandled content block: ${JSON.stringify(value)}`);
}

function Heading({
    level,
    children,
}: {
    level: "h2" | "h3" | "h4";
    children: ReactNode;
}) {
    const className =
        "scroll-mt-24 text-balance font-semibold tracking-tight text-stone-950";
    switch (level) {
        case "h2":
            return (
                <h2 className={`${className} mt-14 text-3xl`}>{children}</h2>
            );
        case "h3":
            return (
                <h3 className={`${className} mt-10 text-2xl`}>{children}</h3>
            );
        case "h4":
            return <h4 className={`${className} mt-8 text-xl`}>{children}</h4>;
        default:
            return assertNever(level);
    }
}

function Gallery({ images }: { images: ContentImageData[] }) {
    return (
        <div
            className="not-prose my-10 grid gap-3 sm:grid-cols-2"
            aria-label="Image gallery"
        >
            {images.map((image) => (
                <figure
                    key={image.id}
                    className="overflow-hidden rounded-xl bg-stone-100"
                >
                    <ContentImage
                        image={image}
                        className="h-full w-full object-cover"
                        sizes="(min-width: 40rem) 23rem, calc(100vw - 2rem)"
                    />
                </figure>
            ))}
        </div>
    );
}

function SafeLink({
    value,
}: {
    value: Extract<ContentBlock, { type: "link" }>["value"];
}) {
    if (!value.href) {
        return <span className="text-stone-500">{value.text}</span>;
    }

    if (value.kind === "internal") {
        if (!value.href.startsWith("/") || value.href.startsWith("//")) {
            return <span className="text-stone-500">{value.text}</span>;
        }
        return (
            <a className="content-link" href={value.href}>
                {value.text}
            </a>
        );
    }

    try {
        const url = new URL(value.href);
        if (url.protocol !== "http:" && url.protocol !== "https:") {
            return <span className="text-stone-500">{value.text}</span>;
        }
    } catch {
        return <span className="text-stone-500">{value.text}</span>;
    }
    return (
        <a
            className="content-link"
            href={value.href}
            target="_blank"
            rel="noopener noreferrer"
        >
            {value.text}
            <span className="sr-only"> (opens in a new tab)</span>
        </a>
    );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
    const highlighted = highlightCode(language, code);
    return (
        <figure className="not-prose my-8 min-w-0 overflow-hidden rounded-xl bg-stone-950 text-stone-100">
            <figcaption className="border-b border-stone-700 px-4 py-2 font-mono text-xs text-stone-300">
                {highlighted.language}
                {!highlighted.supported ? " · plain-text fallback" : ""}
            </figcaption>
            <pre className="max-w-full overflow-x-auto p-4 text-sm leading-6">
                <code>
                    {highlighted.tokens.map((token, index) => (
                        <span
                            className={`code-${token.kind}`}
                            key={`${String(index)}:${String(token.text.length)}`}
                        >
                            {token.text}
                        </span>
                    ))}
                </code>
            </pre>
        </figure>
    );
}

function TableBlock({
    rows,
    header,
}: Extract<ContentBlock, { type: "table" }>["value"]) {
    return (
        <div className="not-prose my-8 max-w-full overflow-x-auto rounded-lg border border-stone-200">
            <table className="w-full min-w-max border-collapse text-left text-sm">
                <tbody>
                    {rows.map((row, rowIndex) => (
                        <tr
                            key={rowIndex}
                            className="border-b border-stone-200 last:border-0"
                        >
                            {row.map((cell, columnIndex) => {
                                const isColumnHeader =
                                    header.row && rowIndex === 0;
                                const isRowHeader =
                                    header.column && columnIndex === 0;
                                const className =
                                    "max-w-80 break-words px-4 py-3 align-top";
                                if (isColumnHeader || isRowHeader) {
                                    return (
                                        <th
                                            key={columnIndex}
                                            scope={
                                                isColumnHeader ? "col" : "row"
                                            }
                                            className={`${className} bg-stone-100 font-semibold text-stone-950`}
                                        >
                                            {cell}
                                        </th>
                                    );
                                }
                                return (
                                    <td
                                        key={columnIndex}
                                        className={`${className} text-stone-700`}
                                    >
                                        {cell}
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export function ContentBlockRenderer({ block }: { block: ContentBlock }) {
    switch (block.type) {
        case "rich_text":
            return (
                <div
                    className="rich-text"
                    // This HTML is author-controlled Wagtail rich text expanded by Django.
                    dangerouslySetInnerHTML={{ __html: block.value.html }}
                />
            );
        case "heading":
            return (
                <Heading level={block.value.level}>{block.value.text}</Heading>
            );
        case "image":
            return (
                <figure className="not-prose my-10 overflow-hidden rounded-xl bg-stone-100">
                    <ContentImage
                        image={block.value}
                        className="h-auto w-full"
                    />
                </figure>
            );
        case "gallery":
            return <Gallery images={block.value.images} />;
        case "quote":
            return (
                <figure className="my-10 border-l-4 border-amber-500 pl-5">
                    <blockquote className="text-xl leading-8 text-stone-800">
                        {block.value.text}
                    </blockquote>
                    {block.value.attribution ? (
                        <figcaption className="mt-3 text-sm text-stone-500">
                            — {block.value.attribution}
                        </figcaption>
                    ) : null}
                </figure>
            );
        case "bulleted_list":
            return (
                <ul className="my-6 list-disc space-y-2 pl-6 marker:text-amber-600">
                    {block.value.items.map((item, index) => (
                        <li key={index}>{item}</li>
                    ))}
                </ul>
            );
        case "numbered_list":
            return (
                <ol className="my-6 list-decimal space-y-2 pl-6 marker:font-semibold marker:text-amber-700">
                    {block.value.items.map((item, index) => (
                        <li key={index}>{item}</li>
                    ))}
                </ol>
            );
        case "checklist":
            return (
                <ul className="not-prose my-6 space-y-3" aria-label="Checklist">
                    {block.value.items.map((item, index) => (
                        <li className="flex items-start gap-3" key={index}>
                            <input
                                type="checkbox"
                                checked={item.checked}
                                disabled
                                aria-label={item.text}
                                className="mt-1 size-4 accent-amber-600"
                            />
                            <span
                                className={
                                    item.checked
                                        ? "text-stone-500 line-through"
                                        : "text-stone-800"
                                }
                            >
                                {item.text}
                            </span>
                        </li>
                    ))}
                </ul>
            );
        case "inline_code":
            return (
                <p className="my-6 min-w-0">
                    <code className="break-all rounded bg-stone-100 px-1.5 py-1 font-mono text-sm text-stone-900">
                        {block.value.code}
                    </code>
                </p>
            );
        case "code_block":
            return (
                <CodeBlock
                    language={block.value.language}
                    code={block.value.code}
                />
            );
        case "table":
            return <TableBlock {...block.value} />;
        case "horizontal_divider":
            return <hr className="my-12 border-stone-300" />;
        case "link":
            return (
                <p className="my-6">
                    <SafeLink value={block.value} />
                </p>
            );
        default:
            return assertNever(block);
    }
}

export function PostBody({ blocks }: { blocks: ContentBlock[] }) {
    return (
        <div className="post-body break-words text-[1.0625rem] leading-8 text-stone-800">
            {blocks.map((block) => (
                <ContentBlockRenderer key={block.id} block={block} />
            ))}
        </div>
    );
}
