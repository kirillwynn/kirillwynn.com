import "server-only";

import {
    deriveInvalidations,
    parseEvent,
    verifySignature,
} from "@/lib/revalidation-contract";

const seenEvents = new Map<string, number>();
const IDEMPOTENCY_TTL_MS = 10 * 60 * 1000;
const MAX_SEEN_EVENTS = 2_000;

export function clearSeenEventsForTests() {
    seenEvents.clear();
}

function pruneSeenEvents(now: number) {
    for (const [id, expiresAt] of seenEvents) {
        if (expiresAt <= now) {
            seenEvents.delete(id);
        }
    }
}

function isDuplicate(eventId: string, now: number): boolean {
    pruneSeenEvents(now);
    return seenEvents.has(eventId);
}

export function markRevalidationDelivered(eventId: string, now = Date.now()) {
    pruneSeenEvents(now);
    if (seenEvents.size >= MAX_SEEN_EVENTS) {
        const oldest = seenEvents.keys().next().value;
        if (oldest) {
            seenEvents.delete(oldest);
        }
    }
    seenEvents.set(eventId, now + IDEMPOTENCY_TTL_MS);
}

export function authenticateRevalidation({
    body,
    timestamp,
    signature,
    secret,
    nowMilliseconds,
    windowSeconds,
}: {
    body: string;
    timestamp: string | null;
    signature: string | null;
    secret: string;
    nowMilliseconds?: number;
    windowSeconds: number;
}) {
    if (
        !verifySignature({
            body,
            timestamp,
            signature,
            secret,
            nowMilliseconds,
            windowSeconds,
        })
    ) {
        return { ok: false as const };
    }
    const event = parseEvent(body);
    if (!event) {
        return { ok: false as const };
    }
    const now = nowMilliseconds ?? Date.now();
    return {
        ok: true as const,
        event,
        duplicate: isDuplicate(event.event_id, now),
        invalidations: deriveInvalidations(event),
    };
}
