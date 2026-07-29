export type ReactionGroup = {
    emoji: string;
    count: number;
    viewer_reacted: boolean;
    participants: string;
};

export type ReactionTarget =
    | {
          kind: "post";
          id: number;
          slug: string;
          returnTo: string;
      }
    | {
          kind: "comment";
          id: number;
          slug: string;
          returnTo: string;
      };

export type ReactionParticipant = {
    id: number;
    display_name: string;
    is_site_author: boolean;
};

export type ReactionParticipantPage = {
    next: string | null;
    previous: string | null;
    results: ReactionParticipant[];
};

export type ReactionConfig = {
    quick_reactions: [string, string, string];
};

export type PostReactionBatchResult = {
    post_id: number;
    slug: string;
    reactions: ReactionGroup[];
};

export type ReactionChange = {
    reactions: ReactionGroup[];
    revision: number;
    source: "optimistic" | "authoritative" | "rollback";
};

type ReactionResponse = {
    action?: "added" | "removed";
    reactions: ReactionGroup[];
};

type PostReactionBatchResponse = {
    results: PostReactionBatchResult[];
};

export const MAX_POST_REACTION_BATCH_IDS = 50;

export class ReactionApiError extends Error {
    constructor(
        message: string,
        readonly status: number,
        readonly retryAfter: number | null = null,
    ) {
        super(message);
    }
}

function reactionPath(target: ReactionTarget): string {
    if (target.kind === "post") {
        return `/api/v1/posts/${encodeURIComponent(target.slug)}/reactions/`;
    }
    return `/api/v1/comments/${String(target.id)}/reactions/`;
}

function togglePath(target: ReactionTarget): string {
    return `${reactionPath(target)}toggle/`;
}

export function reactionParticipantPath(
    target: ReactionTarget,
    emoji: string,
): string {
    return `${reactionPath(target)}${encodeURIComponent(emoji)}/participants/`;
}

async function responseMessage(response: Response): Promise<string> {
    try {
        const payload: unknown = await response.json();
        if (payload && typeof payload === "object") {
            const detail = (payload as { detail?: unknown }).detail;
            if (typeof detail === "string") {
                return detail;
            }
            const emoji = (payload as { emoji?: unknown }).emoji;
            if (Array.isArray(emoji) && typeof emoji[0] === "string") {
                return emoji[0];
            }
        }
    } catch {
        // Keep upstream response bodies out of the UI.
    }
    return response.status === 429
        ? "You are reacting too quickly. Please wait and try again."
        : "The reaction request could not be completed.";
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (!headers.has("Accept")) {
        headers.set("Accept", "application/json");
    }
    const response = await fetch(url, {
        ...options,
        cache: "no-store",
        credentials: "same-origin",
        headers,
    });
    if (!response.ok) {
        const retry = response.headers.get("Retry-After");
        throw new ReactionApiError(
            await responseMessage(response),
            response.status,
            retry && /^\d+$/.test(retry) ? Number(retry) : null,
        );
    }
    return (await response.json()) as T;
}

export async function getPostReactions(
    target: Extract<ReactionTarget, { kind: "post" }>,
): Promise<ReactionGroup[]> {
    return (await request<ReactionResponse>(reactionPath(target))).reactions;
}

export async function getPostReactionBatch(
    postIds: number[],
    signal?: AbortSignal,
): Promise<PostReactionBatchResult[]> {
    if (
        postIds.length === 0 ||
        postIds.length > MAX_POST_REACTION_BATCH_IDS ||
        new Set(postIds).size !== postIds.length ||
        postIds.some((postId) => !Number.isSafeInteger(postId) || postId < 1)
    ) {
        throw new TypeError(
            `postIds must contain 1-${String(MAX_POST_REACTION_BATCH_IDS)} unique positive integers`,
        );
    }
    const ids = postIds.join(",");
    return (
        await request<PostReactionBatchResponse>(
            `/api/v1/reactions/posts/?ids=${ids}`,
            { signal },
        )
    ).results;
}

export async function toggleReaction(
    target: ReactionTarget,
    emoji: string,
    csrfToken: string,
): Promise<ReactionGroup[]> {
    const response = await request<ReactionResponse>(togglePath(target), {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ emoji }),
    });
    return response.reactions;
}

function checkedRelativePath(value: string, expectedPath: string): string {
    if (
        !value.startsWith("/") ||
        value.startsWith("//") ||
        value.includes("\\")
    ) {
        throw new ReactionApiError("The participants cursor is invalid.", 400);
    }
    const url = new URL(value, "https://reactions.invalid");
    if (url.pathname !== expectedPath || url.hash) {
        throw new ReactionApiError("The participants cursor is invalid.", 400);
    }
    return `${url.pathname}${url.search}`;
}

export function getReactionParticipants(
    target: ReactionTarget,
    emoji: string,
    endpoint: string,
    cursor?: string,
    signal?: AbortSignal,
): Promise<ReactionParticipantPage> {
    const expected = reactionParticipantPath(target, emoji);
    const initial = checkedRelativePath(endpoint, expected);
    return request<ReactionParticipantPage>(
        cursor ? checkedRelativePath(cursor, expected) : initial,
        { signal },
    );
}

let configPromise: Promise<ReactionConfig> | null = null;

export function getReactionConfig(): Promise<ReactionConfig> {
    configPromise ??= request<ReactionConfig>(
        "/api/v1/reactions/config/",
    ).catch((error: unknown) => {
        configPromise = null;
        throw error;
    });
    return configPromise;
}

export function resetReactionConfigForTests(): void {
    configPromise = null;
}
