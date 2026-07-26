const SLUG_PATTERN = /^[\p{L}\p{N}_-]+$/u;
const MAX_SLUG_LENGTH = 255;

export function isValidSlug(value: string): boolean {
    const length = Array.from(value).length;
    return (
        length > 0 &&
        length <= MAX_SLUG_LENGTH &&
        value !== "." &&
        value !== ".." &&
        SLUG_PATTERN.test(value)
    );
}

export function decodeRouteSlug(value: string): string | null {
    try {
        const decoded = decodeURIComponent(value);
        return isValidSlug(decoded) ? decoded : null;
    } catch {
        return null;
    }
}

export function postPath(slug: string): string | null {
    return isValidSlug(slug) ? `/posts/${encodeURIComponent(slug)}` : null;
}
