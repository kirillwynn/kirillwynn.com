"use client";

import {
    QueryClient,
    QueryClientProvider,
    useQueryClient,
} from "@tanstack/react-query";
import {
    createContext,
    type ReactNode,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import type { MeResponse } from "@/lib/auth";

type AuthStatus = "loading" | "ready" | "error";

type AuthContextValue = {
    clearSessionCache: () => void;
    identityKey: string;
    me: MeResponse | null;
    refresh: () => Promise<boolean>;
    status: AuthStatus;
};

const AuthContext = createContext<AuthContextValue>({
    clearSessionCache: () => undefined,
    identityKey: "pending",
    me: null,
    refresh: () => Promise.resolve(false),
    status: "loading",
});

export const ME_QUERY_KEY = ["auth", "me"] as const;

function makeQueryClient(): QueryClient {
    return new QueryClient({
        defaultOptions: {
            queries: {
                gcTime: 30 * 60 * 1000,
                refetchOnReconnect: false,
                refetchOnWindowFocus: false,
                retry: false,
                staleTime: 5 * 60 * 1000,
            },
            mutations: { retry: false },
        },
    });
}

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

async function fetchMe(): Promise<MeResponse> {
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
    return payload;
}

function AuthStateProvider({ children }: { children: ReactNode }) {
    const queryClient = useQueryClient();
    const previousIdentityRef = useRef<string | null>(null);
    const [me, setMe] = useState<MeResponse | null>(
        () => queryClient.getQueryData<MeResponse>(ME_QUERY_KEY) ?? null,
    );
    const [status, setStatus] = useState<AuthStatus>(() =>
        queryClient.getQueryData(ME_QUERY_KEY) ? "ready" : "loading",
    );
    const identityKey =
        status === "ready"
            ? me?.authenticated && me.user
                ? `user:${String(me.user.id)}`
                : "anonymous"
            : "pending";

    const refresh = useCallback(async (): Promise<boolean> => {
        await queryClient.invalidateQueries({
            queryKey: ME_QUERY_KEY,
            exact: true,
            refetchType: "none",
        });
        try {
            const payload = await queryClient.fetchQuery({
                queryKey: ME_QUERY_KEY,
                queryFn: fetchMe,
                staleTime: 0,
            });
            setMe(payload);
            setStatus("ready");
            return true;
        } catch {
            setMe(null);
            setStatus("error");
            return false;
        }
    }, [queryClient]);

    const clearSessionCache = useCallback(() => {
        queryClient.removeQueries({ queryKey: ["viewer"] });
        queryClient.removeQueries({ queryKey: ME_QUERY_KEY });
        setMe(null);
        setStatus("loading");
    }, [queryClient]);

    useEffect(() => {
        if (status === "loading") {
            void refresh();
        }
    }, [refresh, status]);

    useEffect(() => {
        if (status === "loading") {
            return;
        }
        if (previousIdentityRef.current !== identityKey) {
            queryClient.removeQueries({
                predicate: (query) =>
                    query.queryKey[0] === "viewer" &&
                    query.queryKey[1] !== identityKey,
            });
            previousIdentityRef.current = identityKey;
        }
    }, [identityKey, queryClient, status]);

    const value = useMemo(
        () => ({ clearSessionCache, identityKey, me, refresh, status }),
        [clearSessionCache, identityKey, me, refresh, status],
    );
    return (
        <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    );
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [queryClient] = useState(makeQueryClient);
    return (
        <QueryClientProvider client={queryClient}>
            <AuthStateProvider>{children}</AuthStateProvider>
        </QueryClientProvider>
    );
}

export function useAuth(): AuthContextValue {
    return useContext(AuthContext);
}
