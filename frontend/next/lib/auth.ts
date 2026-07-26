export const providerIds = ["google", "github"] as const;

export type ProviderId = (typeof providerIds)[number];

export type ProviderState = {
    available: boolean;
    connected: boolean;
};

export type CurrentUser = {
    id: number;
    display_name: string;
    email: string;
    is_admin: boolean;
    is_banned: boolean;
    can_interact: boolean;
};

export type MeResponse = {
    authenticated: boolean;
    user: CurrentUser | null;
    providers: Record<ProviderId, ProviderState>;
    csrf_token: string;
};

const postPath = /^\/posts\/[\p{L}\p{N}_-]+$/u;

function hasControlCharacter(value: string): boolean {
    return Array.from(value).some((character) => {
        const codePoint = character.codePointAt(0) ?? 0;
        return codePoint <= 31 || codePoint === 127;
    });
}

export function safeReturnTo(
    value: string | null | undefined,
    fallback = "/",
): string {
    if (!value || hasControlCharacter(value) || value.includes("\\")) {
        return fallback;
    }

    let decoded: string;
    try {
        decoded = decodeURIComponent(value);
        if (decodeURIComponent(decoded) !== decoded) {
            return fallback;
        }
    } catch {
        return fallback;
    }
    if (hasControlCharacter(decoded) || decoded.includes("\\")) {
        return fallback;
    }

    let url: URL;
    try {
        url = new URL(decoded, "https://return-to.invalid");
    } catch {
        return fallback;
    }
    if (
        url.origin !== "https://return-to.invalid" ||
        url.hash ||
        !decoded.startsWith("/") ||
        decoded.startsWith("//")
    ) {
        return fallback;
    }

    const pathname = decodeURIComponent(url.pathname);
    if (
        pathname === "/" ||
        pathname === "/bridge" ||
        pathname === "/account" ||
        postPath.test(pathname)
    ) {
        return decoded;
    }
    return fallback;
}

export function authErrorMessage(
    error: string | null | undefined,
): string | null {
    if (!error) {
        return null;
    }
    if (error === "cancelled") {
        return "Sign-in was cancelled. You can try again whenever you are ready.";
    }
    if (error === "verified_email_required") {
        return "A verified email address from the provider is required.";
    }
    if (error === "account_unavailable") {
        return "This account is unavailable.";
    }
    if (error === "provider_unavailable") {
        return "This sign-in provider is temporarily unavailable.";
    }
    if (error === "already_connected") {
        return "That provider is already connected to this account.";
    }
    if (error === "identity_in_use") {
        return "That provider identity belongs to another account.";
    }
    return "Sign-in could not be completed. Please try again.";
}
