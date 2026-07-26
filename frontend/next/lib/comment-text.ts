export const COMMENT_BODY_CODE_POINT_LIMIT = 5000;

export function codePointLength(value: string): number {
    return Array.from(value).length;
}

export function truncateCodePoints(
    value: string,
    limit = COMMENT_BODY_CODE_POINT_LIMIT,
): string {
    if (!Number.isSafeInteger(limit) || limit < 0) {
        throw new RangeError(
            "The code-point limit must be a non-negative integer.",
        );
    }

    let codePoints = 0;
    let end = 0;
    for (const codePoint of value) {
        if (codePoints === limit) {
            break;
        }
        end += codePoint.length;
        codePoints += 1;
    }
    return end === value.length ? value : value.slice(0, end);
}
