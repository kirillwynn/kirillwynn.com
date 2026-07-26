export type CommentStatus = "visible" | "deleted" | "hidden";

export type CommentAuthor = {
    id: number;
    display_name: string;
    is_site_author: boolean;
};

export type CommentViewer = {
    can_edit: boolean;
    can_delete: boolean;
    can_reply: boolean;
};

export type PublicComment = {
    id: number;
    kind: "comment" | "reply";
    body: string | null;
    status: CommentStatus;
    author: CommentAuthor;
    thread_root_id: number | null;
    reply_to: { id: number; display_name: string } | null;
    created_at: string;
    updated_at: string;
    edited_at: string | null;
    reply_count: number;
    last_reply_at: string | null;
    viewer: CommentViewer;
};

export type CommentPage = {
    next: string | null;
    previous: string | null;
    results: PublicComment[];
};

export type ThreadPage = CommentPage & {
    root: PublicComment;
};

export class CommentApiError extends Error {
    constructor(
        message: string,
        readonly status: number,
        readonly retryAfter: number | null = null,
    ) {
        super(message);
    }
}

function commentListPath(slug: string): string {
    return `/api/v1/posts/${encodeURIComponent(slug)}/comments/`;
}

function commentPath(id: number): string {
    return `/api/v1/comments/${String(id)}/`;
}

function threadPath(id: number): string {
    return `/api/v1/comments/${String(id)}/thread/`;
}

function replyPath(id: number): string {
    return `/api/v1/comments/${String(id)}/replies/`;
}

async function errorMessage(response: Response): Promise<string> {
    try {
        const payload: unknown = await response.json();
        if (payload && typeof payload === "object") {
            const detail = (payload as { detail?: unknown }).detail;
            if (typeof detail === "string") {
                return detail;
            }
            const body = (payload as { body?: unknown }).body;
            if (Array.isArray(body) && typeof body[0] === "string") {
                return body[0];
            }
            if (typeof body === "string") {
                return body;
            }
        }
    } catch {
        // A generic message is safer than exposing an upstream response.
    }
    return response.status === 429
        ? "You are commenting too quickly. Please wait and try again."
        : "The comment request could not be completed.";
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
        throw new CommentApiError(
            await errorMessage(response),
            response.status,
            retry && /^\d+$/.test(retry) ? Number(retry) : null,
        );
    }
    if (response.status === 204) {
        return undefined as T;
    }
    return (await response.json()) as T;
}

function mutationOptions(
    method: string,
    body: string,
    csrfToken: string,
): RequestInit {
    return {
        method,
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ body }),
    };
}

export function getComments(
    slug: string,
    cursorUrl?: string,
): Promise<CommentPage> {
    return request<CommentPage>(cursorUrl ?? commentListPath(slug));
}

export function getThread(id: number, cursorUrl?: string): Promise<ThreadPage> {
    return request<ThreadPage>(cursorUrl ?? threadPath(id));
}

export function createComment(
    slug: string,
    body: string,
    csrfToken: string,
): Promise<PublicComment> {
    return request<PublicComment>(
        commentListPath(slug),
        mutationOptions("POST", body, csrfToken),
    );
}

export function createThreadReply(
    targetId: number,
    body: string,
    csrfToken: string,
): Promise<PublicComment> {
    return request<PublicComment>(
        replyPath(targetId),
        mutationOptions("POST", body, csrfToken),
    );
}

export function editPublicComment(
    id: number,
    body: string,
    csrfToken: string,
): Promise<PublicComment> {
    return request<PublicComment>(
        commentPath(id),
        mutationOptions("PATCH", body, csrfToken),
    );
}

export function deletePublicComment(
    id: number,
    csrfToken: string,
): Promise<undefined> {
    return request<undefined>(commentPath(id), {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfToken },
    });
}
