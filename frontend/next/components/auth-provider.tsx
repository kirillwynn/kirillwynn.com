"use client";

import {
    createContext,
    type ReactNode,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react";

import type { MeResponse } from "@/lib/auth";

type AuthStatus = "loading" | "ready" | "error";

type AuthContextValue = {
    me: MeResponse | null;
    refresh: () => Promise<boolean>;
    status: AuthStatus;
};

const AuthContext = createContext<AuthContextValue>({
    me: null,
    refresh: () => Promise.resolve(false),
    status: "loading",
});

function isMeResponse(value: unknown): value is MeResponse {
    if (!value || typeof value !== "object") {
        return false;
    }
    const candidate = value as Partial<MeResponse>;
    const user = candidate.user;
    const providers: unknown = candidate.providers;
    const providerRecord =
        providers && typeof providers === "object"
            ? (providers as Record<string, unknown>)
            : null;
    const validUser =
        user === null ||
        (typeof user === "object" &&
            typeof user.id === "number" &&
            typeof user.nickname === "string" &&
            typeof user.display_name === "string" &&
            (user.nickname_suggestion === null ||
                typeof user.nickname_suggestion === "string") &&
            typeof user.email === "string" &&
            typeof user.email_verified === "boolean" &&
            typeof user.profile_complete === "boolean" &&
            typeof user.has_usable_password === "boolean" &&
            (user.nickname_change_available_at === null ||
                typeof user.nickname_change_available_at === "string") &&
            typeof user.is_admin === "boolean" &&
            typeof user.is_banned === "boolean" &&
            typeof user.can_interact === "boolean");
    return (
        typeof candidate.authenticated === "boolean" &&
        typeof candidate.csrf_token === "string" &&
        validUser &&
        providerRecord !== null &&
        [providerRecord.google, providerRecord.github].every(
            (provider) =>
                Boolean(provider) &&
                typeof provider === "object" &&
                typeof (provider as Record<string, unknown>).available ===
                    "boolean" &&
                typeof (provider as Record<string, unknown>).connected ===
                    "boolean",
        )
    );
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [me, setMe] = useState<MeResponse | null>(null);
    const [status, setStatus] = useState<AuthStatus>("loading");

    const refresh = useCallback(async (): Promise<boolean> => {
        try {
            const response = await fetch("/api/me/", {
                cache: "no-store",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!response.ok) {
                throw new Error("Current-user request failed");
            }
            const payload: unknown = await response.json();
            if (!isMeResponse(payload)) {
                throw new Error("Current-user response was invalid");
            }
            setMe(payload);
            setStatus("ready");
            return true;
        } catch {
            setMe(null);
            setStatus("error");
            return false;
        }
    }, []);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const value = useMemo(
        () => ({ me, refresh, status }),
        [me, refresh, status],
    );
    return (
        <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    );
}

export function useAuth(): AuthContextValue {
    return useContext(AuthContext);
}
