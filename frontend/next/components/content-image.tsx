import type { ContentImage as ContentImageData } from "@/lib/content-contract";

type ContentImageProps = {
    image: ContentImageData;
    className?: string;
    sizes?: string;
    eager?: boolean;
};

export function ContentImage({
    image,
    className,
    sizes = "(min-width: 64rem) 48rem, calc(100vw - 2rem)",
    eager = false,
}: ContentImageProps) {
    const largest = image.renditions["1440w"];
    const srcSet = (["480w", "960w", "1440w"] as const)
        .map((key) => {
            const rendition = image.renditions[key];
            return `${rendition.url} ${String(rendition.width)}w`;
        })
        .join(", ");

    return (
        // The backend owns rendition specs and supplies already-public URLs.
        <img
            src={largest.url}
            srcSet={srcSet}
            sizes={sizes}
            width={largest.width}
            height={largest.height}
            alt={image.decorative ? "" : image.alt}
            className={className}
            loading={eager ? "eager" : "lazy"}
            fetchPriority={eager ? "high" : "auto"}
            decoding="async"
        />
    );
}
