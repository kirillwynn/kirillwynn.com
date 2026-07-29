"use client";

import { ProviderForm } from "@/components/provider-form";
import { useAuth } from "@/components/auth-provider";
import { authErrorMessage, providerIds } from "@/lib/auth";

const providerLabels = { google: "Google", github: "GitHub" } as const;

export function AccountPanel({ error }: { error?: string }) {
    const { me, status } = useAuth();
    const message = authErrorMessage(error);

    if (status === "loading") {
        return <p role="status">Loading account…</p>;
    }
    if (!me?.authenticated || !me.user) {
        return (
            <div className="space-y-4">
                {message ? (
                    <p
                        className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm"
                        role="alert"
                    >
                        {message}
                    </p>
                ) : null}
                <p className="text-stone-700">
                    Sign in to view connected providers.
                </p>
                <a className="button-link" href="/login?next=%2Faccount">
                    Login
                </a>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {message ? (
                <p
                    className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm"
                    role="alert"
                >
                    {message}
                </p>
            ) : null}
            <dl className="grid gap-2 rounded-xl border border-stone-200 bg-[var(--color-surface)] p-5">
                <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                        Name
                    </dt>
                    <dd className="text-stone-950">{me.user.display_name}</dd>
                </div>
                <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                        Email
                    </dt>
                    <dd className="text-stone-700">{me.user.email}</dd>
                </div>
            </dl>
            <section aria-labelledby="connected-providers-heading">
                <h2
                    id="connected-providers-heading"
                    className="text-lg font-semibold text-stone-950"
                >
                    Connected providers
                </h2>
                <ul className="mt-3 grid gap-3">
                    {providerIds.map((provider) => {
                        const state = me.providers[provider];
                        return (
                            <li
                                key={provider}
                                className="flex min-h-14 items-center justify-between gap-4 rounded-xl border border-stone-200 bg-[var(--color-surface)] p-3"
                            >
                                <span className="font-medium">
                                    {providerLabels[provider]}
                                </span>
                                {state.connected ? (
                                    <span className="text-sm font-medium text-emerald-700">
                                        Connected
                                    </span>
                                ) : (
                                    <div className="min-w-36">
                                        <ProviderForm
                                            provider={provider}
                                            available={state.available}
                                            csrfToken={me.csrf_token}
                                            next="/account"
                                            process="connect"
                                        />
                                    </div>
                                )}
                            </li>
                        );
                    })}
                </ul>
            </section>
        </div>
    );
}
