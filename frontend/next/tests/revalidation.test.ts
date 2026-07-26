import { beforeEach, describe, expect, it } from "vitest";

import {
    deriveInvalidations,
    parseEvent,
    signBody,
    verifySignature,
} from "@/lib/revalidation-contract";
import {
    authenticateRevalidation,
    clearSeenEventsForTests,
    markRevalidationDelivered,
} from "@/lib/server/revalidation";

const secret = "test-shared-secret";
const timestamp = "1800000000";
const nowMilliseconds = 1_800_000_000_000;
const body = JSON.stringify({
    action: "updated",
    event_id: "d9428888-122b-4b16-9f86-4d959146b441",
    occurred_at: "2027-01-15T08:00:00Z",
    page_id: 42,
    previous_slug: "old-slug",
    slug: "new-slug",
});

beforeEach(() => {
    clearSeenEventsForTests();
});

describe("signed revalidation", () => {
    it("verifies HMAC over timestamp and exact raw body", () => {
        const signature = signBody(body, timestamp, secret);
        expect(
            verifySignature({
                body,
                timestamp,
                signature,
                secret,
                nowMilliseconds,
            }),
        ).toBe(true);
        expect(
            verifySignature({
                body: `${body} `,
                timestamp,
                signature,
                secret,
                nowMilliseconds,
            }),
        ).toBe(false);
        expect(
            verifySignature({
                body,
                timestamp,
                signature: `${signature.slice(0, -1)}${
                    signature.endsWith("0") ? "1" : "0"
                }`,
                secret,
                nowMilliseconds,
            }),
        ).toBe(false);
    });

    it("rejects stale timestamps", () => {
        expect(
            verifySignature({
                body,
                timestamp,
                signature: signBody(body, timestamp, secret),
                secret,
                nowMilliseconds: nowMilliseconds + 301_000,
                windowSeconds: 300,
            }),
        ).toBe(false);
    });

    it("derives only allowlisted tags and paths from semantic fields", () => {
        const event = parseEvent(body);
        expect(event).not.toBeNull();
        if (!event) {
            throw new Error("Expected a valid event");
        }
        expect(deriveInvalidations(event)).toEqual({
            tags: ["posts", "post:42"],
            paths: ["/", "/posts/new-slug", "/posts/old-slug"],
        });
        expect(
            parseEvent(
                JSON.stringify({
                    ...JSON.parse(body),
                    paths: ["/admin"],
                }),
            ),
        ).toBeNull();
    });

    it("recognizes duplicate event IDs while keeping delivery idempotent", () => {
        const signature = signBody(body, timestamp, secret);
        const input = {
            body,
            timestamp,
            signature,
            secret,
            nowMilliseconds,
            windowSeconds: 300,
        };

        expect(authenticateRevalidation(input)).toMatchObject({
            ok: true,
            duplicate: false,
        });
        markRevalidationDelivered(
            "d9428888-122b-4b16-9f86-4d959146b441",
            nowMilliseconds,
        );
        expect(authenticateRevalidation(input)).toMatchObject({
            ok: true,
            duplicate: true,
        });
    });
});
