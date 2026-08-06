import type { PostListResponse } from "@/lib/content-contract";

const POST_LIST_PATH = "/api/v1/posts/";
const FEED_QUERY_PARAMETERS = new Set(["page", "q"]);

export const PUBLIC_URL_CHANGE_EVENT = "kirillwynn:public-url-change";

function isPositivePage(value: string): boolean {
    return /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value));
}

export function feedApiPath(query: string): string {
    const parameters = new URLSearchParams();
    if (query) {
        parameters.set("q", query);
    }
    const search = parameters.toString();
    return search ? `${POST_LIST_PATH}?${search}` : POST_LIST_PATH;
}

export function checkedNextFeedPath(
    value: string | null,
    query: string,
    origin: string,
    tag?: string,
): string | null {
    if (value === null) {
        return null;
    }
    if (!value.startsWith("/") && !/^https?:\/\//i.test(value)) {
        throw new TypeError("The next Feed page is not a same-origin URL");
    }
    if (value.startsWith("//") || value.includes("\\")) {
        throw new TypeError("The next Feed page is not a safe relative URL");
    }

    const expectedOrigin = new URL(origin).origin;
    const url = new URL(value, expectedOrigin);
    if (
        url.origin !== expectedOrigin ||
        url.username ||
        url.password ||
        url.pathname !== POST_LIST_PATH ||
        url.hash
    ) {
        throw new TypeError(
            "The next Feed page is outside the post-list contract",
        );
    }
    const allowedParameters = tag
        ? new Set([...FEED_QUERY_PARAMETERS, "tag"])
        : FEED_QUERY_PARAMETERS;
    if (
        Array.from(url.searchParams.keys()).some(
            (name) => !allowedParameters.has(name),
        ) ||
        url.searchParams.getAll("page").length !== 1 ||
        url.searchParams.getAll("q").length > 1 ||
        url.searchParams.getAll("tag").length > (tag ? 1 : 0)
    ) {
        throw new TypeError("The next Feed page has invalid parameters");
    }
    const page = url.searchParams.get("page");
    const nextQuery = url.searchParams.get("q") ?? "";
    const nextTag = url.searchParams.get("tag") ?? undefined;
    if (
        !page ||
        !isPositivePage(page) ||
        Number(page) < 2 ||
        nextQuery !== query ||
        nextTag !== tag
    ) {
        throw new TypeError("The next Feed page does not continue this query");
    }
    return `${url.pathname}${url.search}`;
}

function isPostListResponse(value: unknown): value is PostListResponse {
    if (!value || typeof value !== "object") {
        return false;
    }
    const candidate = value as Partial<PostListResponse>;
    return (
        typeof candidate.count === "number" &&
        (candidate.next === null || typeof candidate.next === "string") &&
        (candidate.previous === null ||
            typeof candidate.previous === "string") &&
        Array.isArray(candidate.results)
    );
}

export async function fetchFeedPage(
    path: string,
    query: string,
    signal: AbortSignal,
): Promise<PostListResponse> {
    const origin = window.location.origin;
    const expectedPath =
        path === feedApiPath(query)
            ? path
            : checkedNextFeedPath(path, query, origin);
    if (!expectedPath) {
        throw new TypeError("The Feed page cursor is missing");
    }
    const response = await fetch(expectedPath, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        signal,
    });
    if (!response.ok) {
        throw new Error("The content service did not respond");
    }
    const payload: unknown = await response.json();
    if (!isPostListResponse(payload)) {
        throw new Error("The content service returned an invalid Feed page");
    }
    return {
        ...payload,
        next: checkedNextFeedPath(payload.next, query, origin),
    };
}

export function queryFromLocation(location: Location): string {
    const parameters = new URLSearchParams(location.search);
    const values = parameters.getAll("q");
    return values.length === 1 ? (values[0]?.trim() ?? "") : "";
}
