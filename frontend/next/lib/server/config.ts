import "server-only";

function positiveInteger(value: string | undefined, fallback: number): number {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export function djangoApiUrl(): string {
    return (process.env.DJANGO_API_URL ?? "http://localhost:8000").replace(
        /\/$/,
        "",
    );
}

export function revalidationSecret(): string {
    const secret = process.env.REVALIDATION_SECRET;
    if (!secret) {
        throw new Error("REVALIDATION_SECRET is required at runtime");
    }
    if (Buffer.byteLength(secret, "utf8") < 32) {
        throw new Error("REVALIDATION_SECRET must be at least 32 bytes");
    }
    return secret;
}

export function revalidationWindowSeconds(): number {
    return positiveInteger(
        process.env.REVALIDATION_TIMESTAMP_WINDOW_SECONDS,
        300,
    );
}

export function previewTtlSeconds(): number {
    return positiveInteger(process.env.PREVIEW_TOKEN_TTL_SECONDS, 600);
}

export function previewCookieSecure(): boolean {
    return process.env.NODE_ENV === "production";
}
