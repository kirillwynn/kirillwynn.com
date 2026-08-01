export const providerIds = ["google", "github"] as const;

export type ProviderId = (typeof providerIds)[number];

export type ProviderState = {
    available: boolean;
    connected: boolean;
};

export type CurrentUser = {
    id: number;
    nickname: string;
    display_name: string;
    nickname_suggestion: string | null;
    email: string;
    email_verified: boolean;
    profile_complete: boolean;
    has_usable_password: boolean;
    nickname_change_available_at: string | null;
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

export const authApiPaths = {
    signup: "/api/v1/auth/signup/",
    login: "/api/v1/auth/login/",
    verifyEmail: "/api/v1/auth/verify-email/",
    resendVerification: "/api/v1/auth/verify-email/resend/",
    passwordReset: "/api/v1/auth/password/reset/",
    passwordResetConfirm: "/api/v1/auth/password/reset/confirm/",
    passwordSet: "/api/v1/auth/password/set/",
    passwordChange: "/api/v1/auth/password/change/",
    profile: "/api/v1/auth/profile/",
    logout: "/api/v1/auth/logout/",
} as const;

export type AuthApiPath = (typeof authApiPaths)[keyof typeof authApiPaths];

type ErrorPayload = {
    detail?: unknown;
    errors?: unknown;
    status?: unknown;
    nickname_change_available_at?: unknown;
};

export class AuthApiError extends Error {
    status: number;
    code: string | null;
    retryAfter: number | null;
    fields: Record<string, string[]>;

    constructor(
        message: string,
        status: number,
        {
            code = null,
            fields = {},
            retryAfter = null,
        }: {
            code?: string | null;
            fields?: Record<string, string[]>;
            retryAfter?: number | null;
        } = {},
    ) {
        super(message);
        this.name = "AuthApiError";
        this.status = status;
        this.code = code;
        this.retryAfter = retryAfter;
        this.fields = fields;
    }
}

function errorFields(value: unknown): Record<string, string[]> {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return {};
    }
    const fields: Record<string, string[]> = {};
    for (const [name, messages] of Object.entries(value)) {
        const publicName =
            name === "password1"
                ? "password"
                : name === "password2"
                  ? "password_confirmation"
                  : name;
        if (Array.isArray(messages)) {
            const valid = messages.filter(
                (message): message is string => typeof message === "string",
            );
            if (valid.length > 0) {
                fields[publicName] = valid;
            }
        } else if (typeof messages === "string") {
            fields[publicName] = [messages];
        }
    }
    return fields;
}

export async function authMutation<T>(
    path: AuthApiPath,
    payload: Record<string, unknown>,
    csrfToken: string,
    method: "POST" | "PATCH" = "POST",
): Promise<T> {
    let response: Response;
    try {
        response = await fetch(path, {
            method,
            credentials: "same-origin",
            cache: "no-store",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(payload),
        });
    } catch {
        throw new AuthApiError(
            "The account service could not be reached. Please try again.",
            0,
        );
    }

    let parsed: unknown;
    try {
        parsed = (await response.json()) as unknown;
    } catch {
        parsed = null;
    }
    if (!response.ok) {
        const error =
            parsed !== null && typeof parsed === "object"
                ? (parsed as ErrorPayload)
                : {};
        const fields = errorFields(error.errors ?? error);
        const firstMessages = Object.values(fields).find(
            (messages) => messages.length > 0,
        );
        const firstFieldMessage = firstMessages ? firstMessages[0] : undefined;
        const retryHeader = Number(response.headers.get("Retry-After"));
        throw new AuthApiError(
            typeof error.detail === "string"
                ? error.detail
                : (firstFieldMessage ??
                      (response.status === 403
                          ? "Your session expired or this action is unavailable."
                          : "The request could not be completed.")),
            response.status,
            {
                code: typeof error.status === "string" ? error.status : null,
                fields,
                retryAfter:
                    Number.isFinite(retryHeader) && retryHeader > 0
                        ? retryHeader
                        : null,
            },
        );
    }
    if (parsed === null) {
        return {} as T;
    }
    return parsed as T;
}

const nicknamePunctuation = new Set(["-", "_", ".", "·", "'", "’"]);
const reservedSkeletons = new Set([
    "admin",
    "administrator",
    "moderator",
    "staff",
    "system",
    "support",
]);
const confusables: Record<string, string> = {
    а: "a",
    е: "e",
    о: "o",
    р: "p",
    с: "c",
    х: "x",
    у: "y",
    ѕ: "s",
    і: "i",
    ј: "j",
    һ: "h",
    к: "k",
    ӏ: "l",
    ԁ: "d",
    α: "a",
    ε: "e",
    ι: "i",
    κ: "k",
    ο: "o",
    ρ: "p",
    τ: "t",
    υ: "y",
    χ: "x",
};

function nicknameSkeleton(value: string): string {
    return Array.from(value.normalize("NFKD").toLocaleLowerCase("und"))
        .map((character) => confusables[character] ?? character)
        .filter(
            (character) =>
                !/^\p{M}$/u.test(character) &&
                (/^[\p{L}\p{N}]$/u.test(character) ||
                    nicknamePunctuation.has(character) ||
                    character === " "),
        )
        .filter(
            (character) =>
                character !== " " && !nicknamePunctuation.has(character),
        )
        .join("");
}

function isNoncharacter(codePoint: number): boolean {
    return (
        (codePoint >= 0xfdd0 && codePoint <= 0xfdef) ||
        (codePoint & 0xffff) === 0xfffe ||
        (codePoint & 0xffff) === 0xffff
    );
}

function isDefaultIgnorable(codePoint: number): boolean {
    return [
        [0x034f, 0x034f],
        [0x115f, 0x1160],
        [0x17b4, 0x17b5],
        [0x180b, 0x180f],
        [0x3164, 0x3164],
        [0xfe00, 0xfe0f],
        [0xffa0, 0xffa0],
        [0xe0000, 0xe0fff],
    ].some(([start, end]) => codePoint >= start && codePoint <= end);
}

export function validateNickname(value: string): string | null {
    for (const character of Array.from(value)) {
        const codePoint = character.codePointAt(0) ?? 0;
        if (
            /^[\p{C}\p{Zl}\p{Zp}]$/u.test(character) ||
            isNoncharacter(codePoint) ||
            isDefaultIgnorable(codePoint)
        ) {
            return "Enter a valid nickname.";
        }
    }
    const display = value
        .replace(/\p{Zs}+/gu, " ")
        .trim()
        .normalize("NFC");
    const characters = Array.from(display);
    if (characters.length < 2 || characters.length > 40) {
        return "Nickname must contain between 2 and 40 Unicode characters.";
    }
    if (new TextEncoder().encode(display).length > 160) {
        return "Nickname is too large when encoded.";
    }
    let previousSeparator = false;
    let clusterHasBase = false;
    for (const [index, character] of characters.entries()) {
        const base = /^[\p{L}\p{N}]$/u.test(character);
        const mark = /^\p{M}$/u.test(character);
        const separator =
            character === " " || nicknamePunctuation.has(character);
        if (!(base || mark || separator) || (index === 0 && !base)) {
            return "Nickname must use letters, numbers, spaces, or safe punctuation.";
        }
        if (mark && !clusterHasBase) {
            return "Enter a valid nickname.";
        }
        if (separator && previousSeparator) {
            return "Nickname separators may not be repeated.";
        }
        previousSeparator = separator;
        if (separator) {
            clusterHasBase = false;
        } else if (base) {
            clusterHasBase = true;
        }
    }
    if (previousSeparator) {
        return "Nickname must end with a letter or number.";
    }
    if (reservedSkeletons.has(nicknameSkeleton(display.normalize("NFKC")))) {
        return "This nickname is reserved.";
    }
    return null;
}

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
    if (
        !value ||
        !value.startsWith("/") ||
        value.startsWith("//") ||
        hasControlCharacter(value) ||
        value.includes("\\")
    ) {
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
    if (
        !decoded.startsWith("/") ||
        decoded.startsWith("//") ||
        hasControlCharacter(decoded) ||
        decoded.includes("\\")
    ) {
        return fallback;
    }

    let url: URL;
    try {
        url = new URL(decoded, "https://return-to.invalid");
    } catch {
        return fallback;
    }
    if (url.origin !== "https://return-to.invalid" || url.hash) {
        return fallback;
    }

    const pathname = decoded.split("?", 1)[0];
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

export function localLoginDestination(
    value: string | null | undefined,
    requiresProfileCompletion: boolean,
    fallback = "/",
): string {
    const destination = safeReturnTo(value, fallback);
    return requiresProfileCompletion
        ? `/account/profile?next=${encodeURIComponent(destination)}`
        : destination;
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
    if (error === "identity_mismatch") {
        return "The provider email does not match this account.";
    }
    return "Sign-in could not be completed. Please try again.";
}
