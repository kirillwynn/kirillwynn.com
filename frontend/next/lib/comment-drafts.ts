import {
    COMMENT_BODY_CODE_POINT_LIMIT,
    truncateCodePoints,
} from "@/lib/comment-text";

const PREFIX = "kw:comment-draft:v1";
export const COMMENT_DRAFT_TTL_MS = 24 * 60 * 60 * 1000;
export const COMMENT_DRAFT_MAX_LENGTH = COMMENT_BODY_CODE_POINT_LIMIT;

type DraftKind = "comment" | "reply";
type StoredDraft = {
    body: string;
    savedAt: number;
};

function key(
    slug: string,
    kind: DraftKind,
    threadId: number | null,
    owner: string,
): string {
    const thread = kind === "reply" ? String(threadId) : "root";
    return `${PREFIX}:${encodeURIComponent(slug)}:${kind}:${thread}:${owner}`;
}

function storage(): Storage | null {
    try {
        return window.sessionStorage;
    } catch {
        return null;
    }
}

export function saveCommentDraft({
    slug,
    kind,
    threadId = null,
    userId,
    body,
    now = Date.now(),
}: {
    slug: string;
    kind: DraftKind;
    threadId?: number | null;
    userId: number | null;
    body: string;
    now?: number;
}): void {
    const target = storage();
    if (!target) {
        return;
    }
    const normalized = truncateCodePoints(body, COMMENT_BODY_CODE_POINT_LIMIT);
    const draftKey = key(
        slug,
        kind,
        threadId,
        userId === null ? "pending-auth" : `user-${String(userId)}`,
    );
    if (!normalized) {
        target.removeItem(draftKey);
        return;
    }
    target.setItem(
        draftKey,
        JSON.stringify({ body: normalized, savedAt: now }),
    );
}

export function loadCommentDraft({
    slug,
    kind,
    threadId = null,
    userId,
    now = Date.now(),
}: {
    slug: string;
    kind: DraftKind;
    threadId?: number | null;
    userId: number | null;
    now?: number;
}): string {
    const target = storage();
    if (!target) {
        return "";
    }
    const draftStorage = target;
    const pendingKey = key(slug, kind, threadId, "pending-auth");
    const userKey =
        userId === null
            ? null
            : key(slug, kind, threadId, `user-${String(userId)}`);

    function validDraft(draftKey: string): StoredDraft | null {
        const raw = draftStorage.getItem(draftKey);
        if (!raw) {
            return null;
        }
        try {
            const draft = JSON.parse(raw) as Partial<StoredDraft>;
            if (
                typeof draft.body !== "string" ||
                typeof draft.savedAt !== "number" ||
                !Number.isFinite(draft.savedAt) ||
                now - draft.savedAt > COMMENT_DRAFT_TTL_MS ||
                now < draft.savedAt
            ) {
                draftStorage.removeItem(draftKey);
                return null;
            }
            return {
                body: truncateCodePoints(
                    draft.body,
                    COMMENT_BODY_CODE_POINT_LIMIT,
                ),
                savedAt: draft.savedAt,
            };
        } catch {
            draftStorage.removeItem(draftKey);
            return null;
        }
    }

    const pending = validDraft(pendingKey);
    if (!userKey) {
        return pending?.body ?? "";
    }
    const userDraft = validDraft(userKey);
    const selected =
        pending && (!userDraft || pending.savedAt >= userDraft.savedAt)
            ? pending
            : userDraft;
    if (!selected) {
        return "";
    }
    draftStorage.setItem(
        userKey,
        JSON.stringify({
            body: selected.body,
            savedAt: selected.savedAt,
        }),
    );
    draftStorage.removeItem(pendingKey);
    return selected.body;
}

export function clearCommentDraft({
    slug,
    kind,
    threadId = null,
    userId,
}: {
    slug: string;
    kind: DraftKind;
    threadId?: number | null;
    userId: number | null;
}): void {
    const target = storage();
    if (!target) {
        return;
    }
    target.removeItem(
        key(
            slug,
            kind,
            threadId,
            userId === null ? "pending-auth" : `user-${String(userId)}`,
        ),
    );
    if (userId !== null) {
        target.removeItem(key(slug, kind, threadId, "pending-auth"));
    }
}
