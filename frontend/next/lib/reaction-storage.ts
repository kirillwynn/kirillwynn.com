import type { ReactionTarget } from "@/lib/reactions";

const INTENT_STORAGE_VERSION = 3;
const INTENT_PREFIX = "kw:reaction-intent:v3";
const LEGACY_INTENT_PREFIXES = [
    "kw:reaction-intent:v2",
    "kw:reaction-intent:v1",
] as const;
const INTENT_TTL_MS = 10 * 60 * 1000;
const RECENT_KEY = "kw:reaction-recent:v2";
const LEGACY_RECENT_KEY = "kw:reaction-recent:v1";
const RECENT_STORAGE_VERSION = 2;
const RECENT_LIMIT = 12;
const REACTION_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

type PendingReaction = {
    version: 3;
    reactionId: string;
    createdAt: number;
};

type RecentReactions = {
    version: 2;
    reactionIds: string[];
};

export function isValidReactionId(value: unknown): value is string {
    return (
        typeof value === "string" &&
        value.length > 0 &&
        value.length <= 80 &&
        REACTION_ID.test(value)
    );
}

function intentNamespace(userId: number | null): string {
    return userId !== null && Number.isSafeInteger(userId) && userId > 0
        ? `user-${String(userId)}`
        : "pending-auth";
}

function intentPrefix(target: ReactionTarget, userId: number | null): string {
    return [
        INTENT_PREFIX,
        intentNamespace(userId),
        encodeURIComponent(target.slug),
        target.kind,
        String(target.id),
        "",
    ].join(":");
}

function intentKey(
    target: ReactionTarget,
    reactionId: string,
    userId: number | null,
): string {
    return `${intentPrefix(target, userId)}${encodeURIComponent(reactionId)}`;
}

function intentKeys(target: ReactionTarget, userId: number | null): string[] {
    const targetPrefix = intentPrefix(target, userId);
    const keys: string[] = [];
    for (let index = 0; index < sessionStorage.length; index += 1) {
        const key = sessionStorage.key(index);
        if (key?.startsWith(targetPrefix)) {
            keys.push(key);
        }
    }
    return keys;
}

function clearLegacyIntents(target: ReactionTarget): void {
    for (const prefix of LEGACY_INTENT_PREFIXES) {
        const targetPrefix = [
            prefix,
            encodeURIComponent(target.slug),
            target.kind,
            String(target.id),
            "",
        ].join(":");
        for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
            const key = sessionStorage.key(index);
            if (key?.startsWith(targetPrefix)) {
                sessionStorage.removeItem(key);
            }
        }
    }
}

function storePendingReaction(
    target: ReactionTarget,
    pending: PendingReaction,
    userId: number | null,
): void {
    for (const key of intentKeys(target, userId)) {
        sessionStorage.removeItem(key);
    }
    sessionStorage.setItem(
        intentKey(target, pending.reactionId, userId),
        JSON.stringify(pending),
    );
}

function loadPendingRecord(
    target: ReactionTarget,
    now: number,
    userId: number | null,
): PendingReaction | null {
    let newest: (PendingReaction & { key: string }) | null = null;
    for (const key of intentKeys(target, userId)) {
        let parsed: unknown;
        try {
            parsed = JSON.parse(sessionStorage.getItem(key) ?? "") as unknown;
        } catch {
            sessionStorage.removeItem(key);
            continue;
        }
        if (!parsed || typeof parsed !== "object") {
            sessionStorage.removeItem(key);
            continue;
        }
        const candidate = parsed as Partial<PendingReaction>;
        if (
            candidate.version !== INTENT_STORAGE_VERSION ||
            !isValidReactionId(candidate.reactionId) ||
            !Number.isFinite(candidate.createdAt) ||
            key !== intentKey(target, candidate.reactionId, userId) ||
            now - (candidate.createdAt ?? 0) > INTENT_TTL_MS ||
            now < (candidate.createdAt ?? 0)
        ) {
            sessionStorage.removeItem(key);
            continue;
        }
        const valid = candidate as PendingReaction;
        if (
            newest === null ||
            valid.createdAt > newest.createdAt ||
            (valid.createdAt === newest.createdAt && key > newest.key)
        ) {
            newest = { ...valid, key };
        }
    }
    for (const key of intentKeys(target, userId)) {
        if (key !== newest?.key) {
            sessionStorage.removeItem(key);
        }
    }
    return newest
        ? {
              version: newest.version,
              reactionId: newest.reactionId,
              createdAt: newest.createdAt,
          }
        : null;
}

export function savePendingReaction(
    target: ReactionTarget,
    reactionId: string,
    now = Date.now(),
    userId: number | null = null,
): void {
    if (!isValidReactionId(reactionId) || !Number.isFinite(now)) {
        return;
    }
    try {
        clearLegacyIntents(target);
        storePendingReaction(
            target,
            {
                version: INTENT_STORAGE_VERSION,
                reactionId,
                createdAt: now,
            },
            userId,
        );
    } catch {
        // Storage can be unavailable in private or constrained browser modes.
    }
}

export function loadPendingReaction(
    target: ReactionTarget,
    now = Date.now(),
    userId: number | null = null,
): string | null {
    try {
        clearLegacyIntents(target);
        const owned = loadPendingRecord(target, now, userId);
        if (userId !== null) {
            const anonymous = loadPendingRecord(target, now, null);
            const newest =
                anonymous && (!owned || anonymous.createdAt > owned.createdAt)
                    ? anonymous
                    : owned;
            for (const key of intentKeys(target, null)) {
                sessionStorage.removeItem(key);
            }
            if (newest) {
                storePendingReaction(target, newest, userId);
                return newest.reactionId;
            }
            return null;
        }
        return owned?.reactionId ?? null;
    } catch {
        return null;
    }
}

export function clearPendingReaction(
    target: ReactionTarget,
    userId: number | null = null,
): void {
    try {
        clearLegacyIntents(target);
        for (const key of intentKeys(target, userId)) {
            sessionStorage.removeItem(key);
        }
    } catch {
        // Treat unavailable storage as already cleared.
    }
}

export function loadRecentReactions(): string[] {
    try {
        localStorage.removeItem(LEGACY_RECENT_KEY);
        const parsed: unknown = JSON.parse(
            localStorage.getItem(RECENT_KEY) ?? "",
        );
        if (!parsed || typeof parsed !== "object") {
            localStorage.removeItem(RECENT_KEY);
            return [];
        }
        const candidate = parsed as Partial<RecentReactions>;
        if (
            candidate.version !== RECENT_STORAGE_VERSION ||
            !Array.isArray(candidate.reactionIds)
        ) {
            localStorage.removeItem(RECENT_KEY);
            return [];
        }
        return Array.from(
            new Set(candidate.reactionIds.filter(isValidReactionId)),
        ).slice(0, RECENT_LIMIT);
    } catch {
        try {
            localStorage.removeItem(RECENT_KEY);
            localStorage.removeItem(LEGACY_RECENT_KEY);
        } catch {
            // Ignore unavailable storage.
        }
        return [];
    }
}

export function rememberReaction(reactionId: string): string[] {
    if (!isValidReactionId(reactionId)) {
        return loadRecentReactions();
    }
    const recent = [
        reactionId,
        ...loadRecentReactions().filter((value) => value !== reactionId),
    ].slice(0, RECENT_LIMIT);
    try {
        localStorage.setItem(
            RECENT_KEY,
            JSON.stringify({
                version: RECENT_STORAGE_VERSION,
                reactionIds: recent,
            } satisfies RecentReactions),
        );
    } catch {
        // The in-memory result still updates the current picker.
    }
    return recent;
}

export const reactionStorageLimits = {
    intentTtlMs: INTENT_TTL_MS,
    recentLimit: RECENT_LIMIT,
    version: INTENT_STORAGE_VERSION,
};
