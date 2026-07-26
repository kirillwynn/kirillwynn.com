import emojiRegex from "emoji-regex";

import type { ReactionTarget } from "@/lib/reactions";

const INTENT_PREFIX = "kw:reaction-intent:v1";
const INTENT_TTL_MS = 10 * 60 * 1000;
const RECENT_KEY = "kw:reaction-recent:v1";
const RECENT_LIMIT = 12;

type PendingReaction = {
    emoji: string;
    createdAt: number;
};

export function isValidStoredEmoji(value: unknown): value is string {
    if (typeof value !== "string" || !value || value.includes(":")) {
        return false;
    }
    const codePoints = Array.from(value);
    if (
        codePoints.length > 32 ||
        new TextEncoder().encode(value).length > 128 ||
        value.normalize("NFC") !== value
    ) {
        return false;
    }
    if (
        codePoints.some((character) => {
            const codePoint = character.codePointAt(0) ?? 0;
            return (
                /\s/u.test(character) ||
                codePoint <= 31 ||
                codePoint === 127 ||
                (codePoint >= 0xd800 && codePoint <= 0xdfff) ||
                (codePoint >= 0x202a && codePoint <= 0x202e) ||
                (codePoint >= 0x2066 && codePoint <= 0x2069)
            );
        }) ||
        /\p{Emoji_Presentation}\ufe0f/u.test(value)
    ) {
        return false;
    }
    const matches = value.match(emojiRegex());
    return matches?.length === 1 && matches[0] === value;
}

function intentPrefix(target: ReactionTarget): string {
    return [
        INTENT_PREFIX,
        encodeURIComponent(target.slug),
        target.kind,
        String(target.id),
        "",
    ].join(":");
}

function intentKey(target: ReactionTarget, emoji: string): string {
    return `${intentPrefix(target)}${encodeURIComponent(emoji)}`;
}

function intentKeys(target: ReactionTarget): string[] {
    const prefix = intentPrefix(target);
    const keys: string[] = [];
    for (let index = 0; index < sessionStorage.length; index += 1) {
        const key = sessionStorage.key(index);
        if (key?.startsWith(prefix)) {
            keys.push(key);
        }
    }
    return keys;
}

export function savePendingReaction(
    target: ReactionTarget,
    emoji: string,
    now = Date.now(),
): void {
    if (!isValidStoredEmoji(emoji) || !Number.isFinite(now)) {
        return;
    }
    try {
        for (const key of intentKeys(target)) {
            sessionStorage.removeItem(key);
        }
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
    try {
        let newest: (PendingReaction & { key: string }) | null = null;
        for (const key of intentKeys(target)) {
            let parsed: unknown;
            try {
                parsed = JSON.parse(
                    sessionStorage.getItem(key) ?? "",
                ) as unknown;
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
                !isValidStoredEmoji(candidate.emoji) ||
                !Number.isFinite(candidate.createdAt) ||
                key !== intentKey(target, candidate.emoji) ||
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
        if (newest) {
            for (const key of intentKeys(target)) {
                if (key !== newest.key) {
                    sessionStorage.removeItem(key);
                }
            }
            return newest.emoji;
        }
    } catch {
        return null;
    }
    return null;
}

export function clearPendingReaction(target: ReactionTarget): void {
    try {
        for (const key of intentKeys(target)) {
            sessionStorage.removeItem(key);
        }
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
        return Array.from(new Set(parsed.filter(isValidStoredEmoji))).slice(
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
    if (!isValidStoredEmoji(emoji)) {
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
