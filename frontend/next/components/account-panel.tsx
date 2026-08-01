"use client";

import { ProviderForm } from "@/components/provider-form";
import { useAuth } from "@/components/auth-provider";
import {
    AccountLogoutButton,
    ResendVerificationButton,
    SecuritySessionRetry,
} from "@/components/local-auth-forms";
import { authErrorMessage, providerIds } from "@/lib/auth";

const providerLabels = { google: "Google", github: "GitHub" } as const;

export function AccountPanel({
    error,
    status: accountStatus,
}: {
    error?: string;
    status?: string;
}) {
    const { me, status } = useAuth();
    const message = authErrorMessage(error);
    const providerNotice =
        accountStatus === "already_connected"
            ? "That provider is already connected."
            : accountStatus === "connected"
              ? "Provider connected."
              : null;

    if (status === "loading") {
        return <p role="status">Loading account…</p>;
    }
    if (status === "error") {
        return <SecuritySessionRetry />;
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
    const emailVerified = me.user.email_verified;
    const canSetOAuthPassword =
        emailVerified &&
        providerIds.some((provider) => me.providers[provider].connected);

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
            {providerNotice ? (
                <p
                    className="account-notice account-notice--success"
                    role="status"
                >
                    {providerNotice}
                </p>
            ) : null}
            {!me.user.profile_complete ? (
                <div className="account-notice" role="status">
                    <p>
                        Your public profile is incomplete, so comments and
                        reactions are disabled.
                    </p>
                    <a
                        className="mt-3 inline-block font-semibold"
                        href="/account/profile"
                    >
                        Finish profile
                    </a>
                </div>
            ) : null}
            {!me.user.email_verified ? (
                <div className="account-notice" role="status">
                    <p>
                        Verify the primary email before commenting or reacting.
                    </p>
                    <div className="mt-3">
                        <ResendVerificationButton />
                    </div>
                </div>
            ) : null}
            <dl className="grid gap-2 rounded-xl border border-stone-200 bg-[var(--color-surface)] p-5">
                <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                        Public nickname
                    </dt>
                    <dd className="text-stone-950">{me.user.nickname}</dd>
                </div>
                <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                        Email
                    </dt>
                    <dd className="text-stone-700">
                        {me.user.email} ·{" "}
                        {me.user.email_verified ? "Verified" : "Not verified"}
                    </dd>
                </div>
                <div>
                    <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                        Password
                    </dt>
                    <dd className="text-stone-700">
                        {me.user.has_usable_password ? "Set" : "Not set"}
                    </dd>
                </div>
            </dl>
            <section
                className="account-card"
                aria-labelledby="profile-actions-heading"
            >
                <h2
                    id="profile-actions-heading"
                    className="text-lg font-semibold text-stone-950"
                >
                    Profile and password
                </h2>
                <div className="mt-4 flex flex-wrap gap-3">
                    <a className="button-link" href="/account/profile">
                        {me.user.profile_complete
                            ? "Change nickname"
                            : "Finish profile"}
                    </a>
                    {me.user.has_usable_password ? (
                        <a
                            className="button-link"
                            href="/account/password/change"
                        >
                            Change password
                        </a>
                    ) : canSetOAuthPassword ? (
                        <a className="button-link" href="/account/password/set">
                            Set password
                        </a>
                    ) : (
                        <span className="text-sm text-stone-600">
                            Password setup requires a verified connected
                            provider.
                        </span>
                    )}
                </div>
                {me.user.nickname_change_available_at ? (
                    <p className="mt-3 text-sm text-stone-600">
                        Next nickname change:{" "}
                        {new Date(
                            me.user.nickname_change_available_at,
                        ).toLocaleString()}
                    </p>
                ) : null}
            </section>
            <section aria-labelledby="connected-providers-heading">
                <h2
                    id="connected-providers-heading"
                    className="text-lg font-semibold text-stone-950"
                >
                    Connected providers
                </h2>
                {!me.user.email_verified ? (
                    <p className="mt-2 text-sm text-stone-600" role="status">
                        Verify the primary email before connecting another
                        provider.
                    </p>
                ) : null}
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
                                            available={
                                                state.available && emailVerified
                                            }
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
            <section
                className="border-t border-stone-200 pt-5"
                aria-label="Session"
            >
                <AccountLogoutButton />
            </section>
        </div>
    );
}
