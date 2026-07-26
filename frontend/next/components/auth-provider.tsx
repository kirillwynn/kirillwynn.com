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
    refresh: () => Promise<void>;
    status: AuthStatus;
};

const AuthContext = createContext<AuthContextValue>({
    me: null,
    refresh: () => Promise.resolve(),
    status: "loading",
});

function isMeResponse(value: unknown): value is MeResponse {
    if (!value || typeof value !== "object") {
        return false;
    }
    const candidate = value as Partial<MeResponse>;
    return (
        typeof candidate.authenticated === "boolean" &&
        typeof candidate.csrf_token === "string" &&
        candidate.providers !== undefined &&
        "google" in candidate.providers &&
        "github" in candidate.providers
    );
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [me, setMe] = useState<MeResponse | null>(null);
    const [status, setStatus] = useState<AuthStatus>("loading");

    const refresh = useCallback(async () => {
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
        } catch {
            setMe(null);
            setStatus("error");
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
