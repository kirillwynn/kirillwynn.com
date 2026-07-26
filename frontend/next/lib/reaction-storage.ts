import type { ReactionTarget } from "@/lib/reactions";

const INTENT_PREFIX = "kw:reaction-intent:v1";
const INTENT_TTL_MS = 10 * 60 * 1000;
const RECENT_KEY = "kw:reaction-recent:v1";
const RECENT_LIMIT = 12;

type PendingReaction = {
    emoji: string;
    createdAt: number;
};

function safeEmoji(value: unknown): value is string {
    if (typeof value !== "string" || !value || value.includes(":")) {
        return false;
    }
    const codePoints = Array.from(value);
    if (
        codePoints.length > 32 ||
        new TextEncoder().encode(value).length > 128
    ) {
        return false;
    }
    return (
        !codePoints.some((character) => {
            const codePoint = character.codePointAt(0) ?? 0;
            return (
                /\s/u.test(character) ||
                codePoint <= 31 ||
                codePoint === 127 ||
                (codePoint >= 0x202a && codePoint <= 0x202e) ||
                (codePoint >= 0x2066 && codePoint <= 0x2069)
            );
        }) &&
        Array.from(
            new Intl.Segmenter(undefined, {
                granularity: "grapheme",
            }).segment(value),
        ).length === 1 &&
        (/\p{Extended_Pictographic}/u.test(value) ||
            /^[\u{1f1e6}-\u{1f1ff}]{2}$/u.test(value) ||
            /^[#*0-9]\ufe0f?\u20e3$/u.test(value))
    );
}

function intentKey(target: ReactionTarget, emoji: string): string {
    return [
        INTENT_PREFIX,
        encodeURIComponent(target.slug),
        target.kind,
        String(target.id),
        encodeURIComponent(emoji),
    ].join(":");
}

export function savePendingReaction(
    target: ReactionTarget,
    emoji: string,
    now = Date.now(),
): void {
    if (!safeEmoji(emoji)) {
        return;
    }
    try {
        sessionStorage.setItem(
            intentKey(target, emoji),
            JSON.stringify({ emoji, createdAt: now } satisfies PendingReaction),
        );
    } catch {
        // Storage can be unavailable in private or constrained browser modes.
    }
}

export function loadPendingReaction(
    target: ReactionTarget,
    now = Date.now(),
): string | null {
    const targetPrefix = [
        INTENT_PREFIX,
        encodeURIComponent(target.slug),
        target.kind,
        String(target.id),
        "",
    ].join(":");
    try {
        for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
            const key = sessionStorage.key(index);
            if (!key?.startsWith(targetPrefix)) {
                continue;
            }
            let parsed: PendingReaction;
            try {
                parsed = JSON.parse(
                    sessionStorage.getItem(key) ?? "",
                ) as PendingReaction;
            } catch {
                sessionStorage.removeItem(key);
                continue;
            }
            if (
                !safeEmoji(parsed.emoji) ||
                !Number.isFinite(parsed.createdAt) ||
                now - parsed.createdAt > INTENT_TTL_MS ||
                now < parsed.createdAt
            ) {
                sessionStorage.removeItem(key);
                continue;
            }
            return parsed.emoji;
        }
    } catch {
        return null;
    }
    return null;
}

export function clearPendingReaction(
    target: ReactionTarget,
    emoji: string,
): void {
    try {
        sessionStorage.removeItem(intentKey(target, emoji));
    } catch {
        // Treat unavailable storage as already cleared.
    }
}

export function loadRecentReactions(): string[] {
    try {
        const parsed: unknown = JSON.parse(
            localStorage.getItem(RECENT_KEY) ?? "[]",
        );
        if (!Array.isArray(parsed)) {
            localStorage.removeItem(RECENT_KEY);
            return [];
        }
        return Array.from(new Set(parsed.filter(safeEmoji))).slice(
            0,
            RECENT_LIMIT,
        );
    } catch {
        try {
            localStorage.removeItem(RECENT_KEY);
        } catch {
            // Ignore unavailable storage.
        }
        return [];
    }
}

export function rememberReaction(emoji: string): string[] {
    if (!safeEmoji(emoji)) {
        return loadRecentReactions();
    }
    const recent = [
        emoji,
        ...loadRecentReactions().filter((value) => value !== emoji),
    ].slice(0, RECENT_LIMIT);
    try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
    } catch {
        // The in-memory result still updates the current picker.
    }
    return recent;
}

export const reactionStorageLimits = {
    intentTtlMs: INTENT_TTL_MS,
    recentLimit: RECENT_LIMIT,
};
