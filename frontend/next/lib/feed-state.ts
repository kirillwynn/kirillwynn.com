export const MAX_QUERY_CODE_POINTS = 200;
export const MAX_TAG_CODE_POINTS = 100;

export type FeedState = {
    page: number;
    q?: string;
    tag?: string;
};

export type FeedStateParseResult =
    | { valid: true; state: FeedState }
    | { valid: false };

type SearchParams = Record<string, string | string[] | undefined>;

const ALLOWED_PARAMETERS = new Set(["page", "q", "tag"]);
const UNICODE_SLUG = /^[-_\p{L}\p{N}]+$/u;
const CONTROL_CHARACTER = /\p{C}/u;

function oneValue(value: string | string[] | undefined): string | undefined {
    return Array.isArray(value) ? undefined : value;
}

function hasRepeatedValue(value: string | string[] | undefined): boolean {
    return Array.isArray(value);
}

function codePointLength(value: string): number {
    return Array.from(value).length;
}

export function parseFeedState(params: SearchParams): FeedStateParseResult {
    if (Object.keys(params).some((name) => !ALLOWED_PARAMETERS.has(name))) {
        return { valid: false };
    }
    if (
        hasRepeatedValue(params.page) ||
        hasRepeatedValue(params.q) ||
        hasRepeatedValue(params.tag)
    ) {
        return { valid: false };
    }

    const pageValue = oneValue(params.page);
    const page =
        pageValue === undefined
            ? 1
            : /^[1-9]\d*$/.test(pageValue)
              ? Number(pageValue)
              : Number.NaN;
    if (!Number.isSafeInteger(page)) {
        return { valid: false };
    }

    const rawQuery = oneValue(params.q);
    const q = rawQuery?.trim();
    if (
        (rawQuery !== undefined && CONTROL_CHARACTER.test(rawQuery)) ||
        (q !== undefined && codePointLength(q) > MAX_QUERY_CODE_POINTS)
    ) {
        return { valid: false };
    }

    const rawTag = oneValue(params.tag);
    const tag = rawTag?.trim();
    if (
        (rawTag !== undefined && CONTROL_CHARACTER.test(rawTag)) ||
        (tag !== undefined &&
            tag !== "" &&
            (codePointLength(tag) > MAX_TAG_CODE_POINTS ||
                !UNICODE_SLUG.test(tag)))
    ) {
        return { valid: false };
    }

    return {
        valid: true,
        state: {
            page,
            ...(q ? { q } : {}),
            ...(tag ? { tag } : {}),
        },
    };
}

export function feedHref(state: FeedState): string {
    const params = new URLSearchParams();
    if (state.q) {
        params.set("q", state.q);
    }
    if (state.tag) {
        params.set("tag", state.tag);
    }
    if (state.page > 1) {
        params.set("page", String(state.page));
    }
    const query = params.toString();
    return query ? `/?${query}` : "/";
}
