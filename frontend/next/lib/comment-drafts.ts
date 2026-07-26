const PREFIX = "kw:comment-draft:v1";
export const COMMENT_DRAFT_TTL_MS = 24 * 60 * 60 * 1000;
export const COMMENT_DRAFT_MAX_LENGTH = 5000;

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
    const normalized = body.slice(0, COMMENT_DRAFT_MAX_LENGTH);
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
    userId: number;
    now?: number;
}): string {
    const target = storage();
    if (!target) {
        return "";
    }
    const userKey = key(slug, kind, threadId, `user-${String(userId)}`);
    const pendingKey = key(slug, kind, threadId, "pending-auth");
    const candidateKey = target.getItem(userKey) ? userKey : pendingKey;
    const raw = target.getItem(candidateKey);
    if (!raw) {
        return "";
    }
    try {
        const draft = JSON.parse(raw) as Partial<StoredDraft>;
        if (
            typeof draft.body !== "string" ||
            typeof draft.savedAt !== "number" ||
            now - draft.savedAt > COMMENT_DRAFT_TTL_MS ||
            now < draft.savedAt
        ) {
            target.removeItem(candidateKey);
            return "";
        }
        const body = draft.body.slice(0, COMMENT_DRAFT_MAX_LENGTH);
        if (candidateKey === pendingKey) {
            target.setItem(
                userKey,
                JSON.stringify({ body, savedAt: draft.savedAt }),
            );
            target.removeItem(pendingKey);
        }
        return body;
    } catch {
        target.removeItem(candidateKey);
        return "";
    }
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
