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

export function publicSiteUrl(): string {
    const configured = process.env.PUBLIC_SITE_URL?.trim() || undefined;
    if (!configured && process.env.NODE_ENV === "production") {
        throw new Error("PUBLIC_SITE_URL is required in production");
    }

    const value = configured ?? "http://localhost:3000";
    let url: URL;
    try {
        url = new URL(value);
    } catch {
        throw new Error("PUBLIC_SITE_URL must be a valid HTTP(S) origin");
    }

    if (
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password ||
        url.pathname !== "/" ||
        url.search ||
        url.hash
    ) {
        throw new Error("PUBLIC_SITE_URL must be an HTTP(S) origin");
    }
    return url.origin;
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
