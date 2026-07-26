import { describe, expect, it } from "vitest";

import { decodeRouteSlug, isValidSlug } from "@/lib/slug";

describe("Unicode route slugs", () => {
    it("decodes a Next route segment exactly once", () => {
        expect(
            decodeRouteSlug(
                "%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80",
            ),
        ).toBe("привет-мир");
        expect(decodeRouteSlug("привет-мир")).toBe("привет-мир");
    });

    it.each([
        "",
        ".",
        "..",
        "with/slash",
        "with%2Fslash",
        "with\\backslash",
        "control\u0000character",
        "%00control",
        "%E0%A4%A",
        "a".repeat(256),
    ])("rejects unsafe or malformed route slug %j", (slug) => {
        expect(decodeRouteSlug(slug)).toBeNull();
    });

    it("uses the same slug rules as signed revalidation", () => {
        expect(isValidSlug("пост_2026-日本語")).toBe(true);
        expect(isValidSlug("not.allowed")).toBe(false);
    });
});
