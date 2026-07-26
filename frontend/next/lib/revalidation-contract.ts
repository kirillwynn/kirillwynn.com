import { createHmac, timingSafeEqual } from "node:crypto";

import { isValidSlug } from "@/lib/slug";

export const REVALIDATION_ACTIONS = [
    "published",
    "updated",
    "unpublished",
    "expired",
] as const;

export type RevalidationEvent = {
    event_id: string;
    action: (typeof REVALIDATION_ACTIONS)[number];
    page_id: number;
    slug: string;
    previous_slug?: string;
    occurred_at: string;
};

const EVENT_KEYS = new Set([
    "event_id",
    "action",
    "page_id",
    "slug",
    "previous_slug",
    "occurred_at",
]);
const UUID_PATTERN =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SIGNATURE_PATTERN = /^v1=([0-9a-f]{64})$/;

export function signBody(
    body: string,
    timestamp: string,
    secret: string,
): string {
    return `v1=${createHmac("sha256", secret)
        .update(`${timestamp}.${body}`, "utf8")
        .digest("hex")}`;
}

export function verifySignature({
    body,
    timestamp,
    signature,
    secret,
    nowMilliseconds = Date.now(),
    windowSeconds = 300,
}: {
    body: string;
    timestamp: string | null;
    signature: string | null;
    secret: string;
    nowMilliseconds?: number;
    windowSeconds?: number;
}): boolean {
    if (!/^\d{10}$/.test(timestamp ?? "")) {
        return false;
    }
    const sentAt = Number(timestamp) * 1000;
    if (Math.abs(nowMilliseconds - sentAt) > windowSeconds * 1000) {
        return false;
    }
    const match = SIGNATURE_PATTERN.exec(signature ?? "");
    if (!match) {
        return false;
    }
    const expected = Buffer.from(
        signBody(body, timestamp as string, secret).slice(3),
        "hex",
    );
    const supplied = Buffer.from(match[1], "hex");
    return (
        expected.length === supplied.length &&
        timingSafeEqual(expected, supplied)
    );
}

export function parseEvent(body: string): RevalidationEvent | null {
    let value: unknown;
    try {
        value = JSON.parse(body);
    } catch {
        return null;
    }
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return null;
    }
    const record = value as Record<string, unknown>;
    if (Object.keys(record).some((key) => !EVENT_KEYS.has(key))) {
        return null;
    }
    if (
        typeof record.event_id !== "string" ||
        !UUID_PATTERN.test(record.event_id) ||
        typeof record.action !== "string" ||
        !REVALIDATION_ACTIONS.includes(
            record.action as RevalidationEvent["action"],
        ) ||
        typeof record.page_id !== "number" ||
        !Number.isSafeInteger(record.page_id) ||
        record.page_id <= 0 ||
        typeof record.slug !== "string" ||
        !isValidSlug(record.slug) ||
        (record.previous_slug !== undefined &&
            (typeof record.previous_slug !== "string" ||
                !isValidSlug(record.previous_slug))) ||
        typeof record.occurred_at !== "string" ||
        Number.isNaN(Date.parse(record.occurred_at))
    ) {
        return null;
    }
    return {
        event_id: record.event_id,
        action: record.action as RevalidationEvent["action"],
        page_id: record.page_id,
        slug: record.slug,
        ...(record.previous_slug
            ? { previous_slug: record.previous_slug }
            : {}),
        occurred_at: record.occurred_at,
    };
}

export function deriveInvalidations(event: RevalidationEvent) {
    const tags = [
        "posts",
        `post:${String(event.page_id)}`,
        `post-slug:${event.slug}`,
    ];
    const paths = ["/", `/posts/${event.slug}`];
    if (event.previous_slug && event.previous_slug !== event.slug) {
        tags.push(`post-slug:${event.previous_slug}`);
        paths.push(`/posts/${event.previous_slug}`);
    }
    return { tags, paths };
}
