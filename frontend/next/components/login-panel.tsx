"use client";

import Link from "next/link";

import { ProviderForm } from "@/components/provider-form";
import { useAuth } from "@/components/auth-provider";
import {
    LocalLoginForm,
    SecuritySessionRetry,
} from "@/components/local-auth-forms";
import { authErrorMessage, providerIds, safeReturnTo } from "@/lib/auth";

export function LoginPanel({ error, next }: { error?: string; next?: string }) {
    const { me, status } = useAuth();
    const returnTo = safeReturnTo(next);
    const message = authErrorMessage(error);

    if (status === "loading") {
        return (
            <p className="text-sm text-stone-600" role="status">
                Loading sign-in options…
            </p>
        );
    }

    if (me?.authenticated && me.user) {
        return (
            <div className="space-y-4">
                <p className="text-stone-700">
                    Signed in as{" "}
                    <span className="font-semibold text-stone-950">
                        {me.user.display_name}
                    </span>
                    .
                </p>
                <Link className="button-link" href="/account" prefetch={false}>
                    Open account
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-5">
            {message ? (
                <p
                    className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"
                    role="alert"
                >
                    {message}
                </p>
            ) : null}
            {status === "error" ? <SecuritySessionRetry /> : null}
            <LocalLoginForm next={returnTo} />
            <div className="account-divider" role="separator">
                <span>or continue with</span>
            </div>
            <div className="grid gap-3">
                {providerIds.map((provider) => (
                    <ProviderForm
                        key={provider}
                        provider={provider}
                        available={
                            status === "ready" &&
                            Boolean(me?.providers[provider].available)
                        }
                        csrfToken={me?.csrf_token ?? ""}
                        next={returnTo}
                    />
                ))}
            </div>
        </div>
    );
}
