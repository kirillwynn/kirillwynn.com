"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
    AuthApiError,
    authApiPaths,
    authMutation,
    localLoginDestination,
    providerIds,
    safeReturnTo,
    validateNickname,
} from "@/lib/auth";

type FieldErrors = Partial<Record<string, string[]>>;

function describedBy(
    ...values: Array<string | false | undefined>
): string | undefined {
    const ids = values.filter((value): value is string => Boolean(value));
    return ids.length ? ids.join(" ") : undefined;
}

function requestError(error: unknown): {
    message: string;
    fields: FieldErrors;
} {
    if (error instanceof AuthApiError) {
        const retry = error.retryAfter
            ? ` Try again in about ${String(error.retryAfter)} seconds.`
            : "";
        return { message: `${error.message}${retry}`, fields: error.fields };
    }
    return {
        message: "The account service could not be reached. Please try again.",
        fields: {},
    };
}

function FieldError({
    id,
    messages,
}: {
    id: string;
    messages: string[] | undefined;
}) {
    if (!messages?.length) {
        return null;
    }
    return (
        <p className="account-field-error" id={id}>
            {messages[0]}
        </p>
    );
}

function ErrorNotice({ message }: { message: string | null }) {
    const ref = useRef<HTMLParagraphElement>(null);
    useEffect(() => {
        if (message) {
            ref.current?.focus();
        }
    }, [message]);
    return message ? (
        <p
            className="account-notice account-notice--error"
            ref={ref}
            role="alert"
            tabIndex={-1}
        >
            {message}
        </p>
    ) : null;
}

export function SecuritySessionRetry() {
    const { refresh, status } = useAuth();
    const [pending, setPending] = useState(false);

    if (status !== "error") {
        return null;
    }
    return (
        <div className="account-notice account-notice--error" role="alert">
            <p>The account security session could not be loaded.</p>
            <button
                className="button-link mt-3"
                disabled={pending}
                onClick={() => {
                    setPending(true);
                    void refresh().finally(() => {
                        setPending(false);
                    });
                }}
                type="button"
            >
                {pending ? "Retrying…" : "Retry account service"}
            </button>
        </div>
    );
}

export function LocalLoginForm({ next }: { next?: string }) {
    const { me, refresh } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fields, setFields] = useState<FieldErrors>({});
    const destination = safeReturnTo(next);
    const emailErrorId = useId();
    const passwordErrorId = useId();

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!me?.csrf_token || pending) {
            return;
        }
        setPending(true);
        setError(null);
        setFields({});
        try {
            const result = await authMutation<{
                status: "authenticated";
                next: string;
                requires_profile_completion: boolean;
                csrf_token: string;
            }>(
                authApiPaths.login,
                { email, password, next: destination },
                me.csrf_token,
            );
            setPassword("");
            await refresh();
            window.location.assign(
                localLoginDestination(
                    result.next,
                    result.requires_profile_completion,
                    destination,
                ),
            );
        } catch (caught) {
            const failure = requestError(caught);
            setPassword("");
            setError(failure.message);
            setFields(failure.fields);
            if (caught instanceof AuthApiError && caught.status === 403) {
                await refresh();
            }
        } finally {
            setPending(false);
        }
    }

    return (
        <form
            className="account-form"
            onSubmit={(event) => {
                void submit(event);
            }}
        >
            <ErrorNotice message={error} />
            <div className="account-field-group">
                <label className="account-label" htmlFor="login-email">
                    Email
                </label>
                <input
                    aria-describedby={fields.email ? emailErrorId : undefined}
                    aria-invalid={Boolean(fields.email)}
                    autoComplete="email"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    id="login-email"
                    inputMode="email"
                    name="email"
                    onChange={(event) => {
                        setEmail(event.target.value);
                    }}
                    required
                    type="email"
                    value={email}
                />
                <FieldError id={emailErrorId} messages={fields.email} />
            </div>
            <div className="account-field-group">
                <label className="account-label" htmlFor="login-password">
                    Password
                </label>
                <input
                    aria-describedby={
                        fields.password ? passwordErrorId : undefined
                    }
                    aria-invalid={Boolean(fields.password)}
                    autoComplete="current-password"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    id="login-password"
                    name="password"
                    onChange={(event) => {
                        setPassword(event.target.value);
                    }}
                    required
                    type="password"
                    value={password}
                />
                <FieldError id={passwordErrorId} messages={fields.password} />
            </div>
            <button
                className="button-link w-full"
                disabled={pending || !me?.csrf_token}
                type="submit"
            >
                {pending ? "Signing in…" : "Login with email"}
            </button>
            <div className="flex flex-wrap justify-between gap-3 text-sm">
                <Link
                    href={`/signup?next=${encodeURIComponent(destination)}`}
                    prefetch={false}
                >
                    Create an account
                </Link>
                <Link href="/account/password/reset" prefetch={false}>
                    Forgot password?
                </Link>
            </div>
        </form>
    );
}

export function SignupForm({ next }: { next?: string }) {
    const { me, refresh } = useAuth();
    const [email, setEmail] = useState("");
    const [nickname, setNickname] = useState("");
    const [password, setPassword] = useState("");
    const [confirmation, setConfirmation] = useState("");
    const [pending, setPending] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fields, setFields] = useState<FieldErrors>({});
    const destination = safeReturnTo(next);
    const emailErrorId = useId();
    const nicknameHelpId = useId();
    const nicknameErrorId = useId();
    const passwordErrorId = useId();
    const confirmationErrorId = useId();

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!me?.csrf_token || pending) {
            return;
        }
        const nicknameError = validateNickname(nickname);
        if (nicknameError) {
            setFields({ nickname: [nicknameError] });
            setError("Check the highlighted nickname field.");
            return;
        }
        setPending(true);
        setError(null);
        setFields({});
        try {
            await authMutation(
                authApiPaths.signup,
                {
                    email,
                    nickname,
                    password,
                    password_confirmation: confirmation,
                },
                me.csrf_token,
            );
            setEmail("");
            setNickname("");
            setPassword("");
            setConfirmation("");
            setSuccess(true);
        } catch (caught) {
            const failure = requestError(caught);
            setPassword("");
            setConfirmation("");
            setError(failure.message);
            setFields(failure.fields);
            if (caught instanceof AuthApiError && caught.status === 403) {
                await refresh();
            }
        } finally {
            setPending(false);
        }
    }

    if (success) {
        return (
            <div className="space-y-5">
                <p
                    className="account-notice account-notice--success"
                    role="status"
                >
                    If the address can be registered, a verification email will
                    be sent. Open that message before signing in.
                </p>
                <Link
                    className="button-link"
                    href={`/login?next=${encodeURIComponent(destination)}`}
                    prefetch={false}
                >
                    Continue to login
                </Link>
            </div>
        );
    }

    return (
        <form
            className="account-form"
            onSubmit={(event) => {
                void submit(event);
            }}
        >
            <ErrorNotice message={error} />
            <SecuritySessionRetry />
            <label className="account-field-group">
                <span className="account-label">Email</span>
                <input
                    aria-describedby={describedBy(fields.email && emailErrorId)}
                    aria-invalid={Boolean(fields.email)}
                    autoComplete="email"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    inputMode="email"
                    name="email"
                    onChange={(event) => {
                        setEmail(event.target.value);
                    }}
                    required
                    type="email"
                    value={email}
                />
                <FieldError id={emailErrorId} messages={fields.email} />
            </label>
            <label className="account-field-group">
                <span className="account-label">Public nickname</span>
                <input
                    aria-describedby={describedBy(
                        nicknameHelpId,
                        fields.nickname && nicknameErrorId,
                    )}
                    aria-invalid={Boolean(fields.nickname)}
                    autoComplete="nickname"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    maxLength={160}
                    name="nickname"
                    onBlur={() => {
                        const message = validateNickname(nickname);
                        setFields((current) => ({
                            ...current,
                            nickname: message ? [message] : [],
                        }));
                    }}
                    onChange={(event) => {
                        setNickname(event.target.value);
                    }}
                    required
                    value={nickname}
                />
                <span className="account-help" id={nicknameHelpId}>
                    2–40 Unicode characters; letters, numbers, spaces and
                    limited punctuation.
                </span>
                <FieldError id={nicknameErrorId} messages={fields.nickname} />
            </label>
            <label className="account-field-group">
                <span className="account-label">Password</span>
                <input
                    aria-describedby={describedBy(
                        fields.password && passwordErrorId,
                    )}
                    aria-invalid={Boolean(fields.password)}
                    autoComplete="new-password"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    name="password"
                    onChange={(event) => {
                        setPassword(event.target.value);
                    }}
                    required
                    type="password"
                    value={password}
                />
                <FieldError id={passwordErrorId} messages={fields.password} />
            </label>
            <label className="account-field-group">
                <span className="account-label">Confirm password</span>
                <input
                    aria-describedby={describedBy(
                        fields.password_confirmation && confirmationErrorId,
                    )}
                    aria-invalid={Boolean(fields.password_confirmation)}
                    autoComplete="new-password"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    name="password_confirmation"
                    onChange={(event) => {
                        setConfirmation(event.target.value);
                    }}
                    required
                    type="password"
                    value={confirmation}
                />
                <FieldError
                    id={confirmationErrorId}
                    messages={fields.password_confirmation}
                />
            </label>
            <button
                className="button-link w-full"
                disabled={pending || !me?.csrf_token}
                type="submit"
            >
                {pending ? "Creating account…" : "Create account"}
            </button>
            <Link
                className="text-sm"
                href={`/login?next=${encodeURIComponent(destination)}`}
                prefetch={false}
            >
                Already have an account? Login
            </Link>
        </form>
    );
}

export function PasswordResetRequestForm() {
    const { me, refresh } = useAuth();
    const [email, setEmail] = useState("");
    const [pending, setPending] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!me?.csrf_token || pending) {
            return;
        }
        setPending(true);
        setError(null);
        try {
            await authMutation(
                authApiPaths.passwordReset,
                { email },
                me.csrf_token,
            );
            setEmail("");
            setSuccess(true);
        } catch (caught) {
            setError(requestError(caught).message);
            if (caught instanceof AuthApiError && caught.status === 403) {
                await refresh();
            }
        } finally {
            setPending(false);
        }
    }

    return (
        <form
            className="account-form"
            onSubmit={(event) => {
                void submit(event);
            }}
        >
            <ErrorNotice message={error} />
            <SecuritySessionRetry />
            {success ? (
                <p
                    className="account-notice account-notice--success"
                    role="status"
                >
                    If the account is eligible, a password-reset email will be
                    sent.
                </p>
            ) : null}
            <label className="account-field-group">
                <span className="account-label">Email</span>
                <input
                    autoComplete="email"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    inputMode="email"
                    name="email"
                    onChange={(event) => {
                        setEmail(event.target.value);
                    }}
                    required
                    type="email"
                    value={email}
                />
            </label>
            <button
                className="button-link"
                disabled={pending || !me?.csrf_token}
                type="submit"
            >
                {pending ? "Requesting…" : "Send reset email"}
            </button>
        </form>
    );
}

export function AccountPasswordForm({ mode }: { mode: "set" | "change" }) {
    const { me, refresh, status: authStatus } = useAuth();
    const [currentPassword, setCurrentPassword] = useState("");
    const [password, setPassword] = useState("");
    const [confirmation, setConfirmation] = useState("");
    const [pending, setPending] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fields, setFields] = useState<FieldErrors>({});
    const currentPasswordErrorId = useId();
    const passwordErrorId = useId();
    const confirmationErrorId = useId();

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!me?.csrf_token || pending) {
            return;
        }
        setPending(true);
        setSuccess(false);
        setError(null);
        setFields({});
        try {
            await authMutation(
                mode === "set"
                    ? authApiPaths.passwordSet
                    : authApiPaths.passwordChange,
                {
                    ...(mode === "change"
                        ? { current_password: currentPassword }
                        : {}),
                    password,
                    password_confirmation: confirmation,
                },
                me.csrf_token,
            );
            setCurrentPassword("");
            setPassword("");
            setConfirmation("");
            setSuccess(true);
            await refresh();
        } catch (caught) {
            const failure = requestError(caught);
            setCurrentPassword("");
            setPassword("");
            setConfirmation("");
            setError(failure.message);
            setFields(failure.fields);
            if (
                caught instanceof AuthApiError &&
                [401, 403].includes(caught.status)
            ) {
                await refresh();
            }
        } finally {
            setPending(false);
        }
    }

    const user = me?.authenticated ? me.user : null;
    const providers = me?.providers;
    const hasConnectedProvider = providers
        ? providerIds.some((provider) => providers[provider].connected)
        : false;
    if (authStatus === "loading") {
        return <p role="status">Loading account…</p>;
    }
    if (authStatus === "error") {
        return <SecuritySessionRetry />;
    }
    if (!user) {
        return (
            <Link
                className="button-link"
                href="/login?next=%2Faccount"
                prefetch={false}
            >
                Login to manage your password
            </Link>
        );
    }
    if (success) {
        return (
            <div className="space-y-5">
                <p
                    className="account-notice account-notice--success"
                    role="status"
                >
                    {mode === "set" ? "Password set." : "Password changed."}{" "}
                    Other sessions are no longer valid.
                </p>
                <Link className="button-link" href="/account" prefetch={false}>
                    Return to account
                </Link>
            </div>
        );
    }
    if (mode === "set" && user.has_usable_password) {
        return (
            <p>
                A password is already set.{" "}
                <Link href="/account/password/change" prefetch={false}>
                    Change it
                </Link>
                .
            </p>
        );
    }
    if (mode === "set" && (!user.email_verified || !hasConnectedProvider)) {
        return (
            <p role="status">
                Password setup requires a verified primary email and a connected
                Google or GitHub identity.
            </p>
        );
    }
    if (mode === "change" && !user.has_usable_password) {
        return (
            <p>
                This account has no local password.{" "}
                <Link href="/account/password/set" prefetch={false}>
                    Set one
                </Link>
                .
            </p>
        );
    }

    return (
        <form
            className="account-form"
            onSubmit={(event) => {
                void submit(event);
            }}
        >
            <ErrorNotice message={error} />
            {mode === "change" ? (
                <label className="account-field-group">
                    <span className="account-label">Current password</span>
                    <input
                        aria-describedby={describedBy(
                            fields.current_password && currentPasswordErrorId,
                        )}
                        aria-invalid={Boolean(fields.current_password)}
                        autoComplete="current-password"
                        className="account-input"
                        disabled={pending || !me?.csrf_token}
                        name="current_password"
                        onChange={(event) => {
                            setCurrentPassword(event.target.value);
                        }}
                        required
                        type="password"
                        value={currentPassword}
                    />
                    <FieldError
                        id={currentPasswordErrorId}
                        messages={fields.current_password}
                    />
                </label>
            ) : null}
            <label className="account-field-group">
                <span className="account-label">New password</span>
                <input
                    aria-describedby={describedBy(
                        fields.password && passwordErrorId,
                    )}
                    aria-invalid={Boolean(fields.password)}
                    autoComplete="new-password"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    name="password"
                    onChange={(event) => {
                        setPassword(event.target.value);
                    }}
                    required
                    type="password"
                    value={password}
                />
                <FieldError id={passwordErrorId} messages={fields.password} />
            </label>
            <label className="account-field-group">
                <span className="account-label">Confirm new password</span>
                <input
                    aria-describedby={describedBy(
                        fields.password_confirmation && confirmationErrorId,
                    )}
                    aria-invalid={Boolean(fields.password_confirmation)}
                    autoComplete="new-password"
                    className="account-input"
                    disabled={pending || !me?.csrf_token}
                    name="password_confirmation"
                    onChange={(event) => {
                        setConfirmation(event.target.value);
                    }}
                    required
                    type="password"
                    value={confirmation}
                />
                <FieldError
                    id={confirmationErrorId}
                    messages={fields.password_confirmation}
                />
            </label>
            <button
                className="button-link"
                disabled={pending || !me?.csrf_token}
                type="submit"
            >
                {pending
                    ? "Saving…"
                    : mode === "set"
                      ? "Set password"
                      : "Change password"}
            </button>
        </form>
    );
}

export function ProfileForm({ next }: { next?: string }) {
    const { me, refresh, status: authStatus } = useAuth();
    const user = me?.authenticated ? me.user : null;
    const [nickname, setNickname] = useState("");
    const [pending, setPending] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [fields, setFields] = useState<FieldErrors>({});
    const initialized = useRef<number | null>(null);
    const nicknameHelpId = useId();
    const nicknameErrorId = useId();
    const destination = safeReturnTo(next);

    useEffect(() => {
        if (user && initialized.current !== user.id) {
            initialized.current = user.id;
            setNickname(user.nickname_suggestion ?? user.nickname);
        }
    }, [user]);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!user || !me?.csrf_token || pending) {
            return;
        }
        const validation = validateNickname(nickname);
        if (validation) {
            setFields({ nickname: [validation] });
            setError("Check the highlighted nickname field.");
            return;
        }
        const completing = !user.profile_complete;
        setPending(true);
        setSuccess(false);
        setError(null);
        setFields({});
        try {
            await authMutation(
                authApiPaths.profile,
                { nickname },
                me.csrf_token,
                "PATCH",
            );
            setSuccess(true);
            await refresh();
            if (completing) {
                window.location.assign(destination);
            }
        } catch (caught) {
            const failure = requestError(caught);
            setError(failure.message);
            setFields(failure.fields);
            if (
                caught instanceof AuthApiError &&
                ([401, 403].includes(caught.status) ||
                    Object.hasOwn(
                        caught.fields,
                        "nickname_change_available_at",
                    ))
            ) {
                await refresh();
            }
        } finally {
            setPending(false);
        }
    }

    if (authStatus === "loading") {
        return <p role="status">Loading account…</p>;
    }
    if (authStatus === "error") {
        return <SecuritySessionRetry />;
    }
    if (!user) {
        return (
            <p>
                <Link
                    className="button-link"
                    href={`/login?next=${encodeURIComponent(destination)}`}
                    prefetch={false}
                >
                    Login to manage your nickname
                </Link>
            </p>
        );
    }

    const cooldown = user.nickname_change_available_at
        ? new Date(user.nickname_change_available_at)
        : null;
    const cooldownActive = Boolean(cooldown && cooldown.getTime() > Date.now());

    return (
        <form
            className="account-form"
            onSubmit={(event) => {
                void submit(event);
            }}
        >
            <ErrorNotice message={error} />
            {success ? (
                <p
                    className="account-notice account-notice--success"
                    role="status"
                >
                    Public nickname saved.
                </p>
            ) : null}
            {!user.profile_complete ? (
                <p className="account-notice" role="status">
                    Choose your public nickname to finish the profile. Reading
                    and account management remain available until then.
                </p>
            ) : null}
            {cooldownActive ? (
                <p className="account-notice" role="status">
                    The next nickname change is available on{" "}
                    {cooldown?.toLocaleString()}.
                </p>
            ) : null}
            <label className="account-field-group">
                <span className="account-label">Public nickname</span>
                <input
                    aria-describedby={describedBy(
                        nicknameHelpId,
                        fields.nickname && nicknameErrorId,
                    )}
                    aria-invalid={Boolean(fields.nickname)}
                    autoComplete="nickname"
                    className="account-input"
                    disabled={pending || cooldownActive}
                    maxLength={160}
                    name="nickname"
                    onChange={(event) => {
                        setNickname(event.target.value);
                    }}
                    required
                    value={nickname}
                />
                <span className="account-help" id={nicknameHelpId}>
                    Your current nickname appears on posts, comments, replies
                    and reactions.
                </span>
                <FieldError id={nicknameErrorId} messages={fields.nickname} />
            </label>
            <button
                className="button-link"
                disabled={pending || cooldownActive || !me?.csrf_token}
                type="submit"
            >
                {pending
                    ? "Saving…"
                    : user.profile_complete
                      ? "Change nickname"
                      : "Finish profile"}
            </button>
        </form>
    );
}

export function ResendVerificationButton() {
    const { me, refresh } = useAuth();
    const user = me?.authenticated ? me.user : null;
    const [pending, setPending] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    if (!user || user.email_verified) {
        return null;
    }
    return (
        <div className="space-y-2">
            <button
                className="button-link"
                disabled={pending || !me?.csrf_token}
                onClick={() => {
                    if (!me?.csrf_token || pending) {
                        return;
                    }
                    setPending(true);
                    setMessage(null);
                    void authMutation(
                        authApiPaths.resendVerification,
                        { email: user.email },
                        me.csrf_token,
                    )
                        .then(() => {
                            setMessage(
                                "If the account is eligible, an email will be sent.",
                            );
                        })
                        .catch(async (caught: unknown) => {
                            setMessage(requestError(caught).message);
                            if (
                                caught instanceof AuthApiError &&
                                caught.status === 403
                            ) {
                                await refresh();
                            }
                        })
                        .finally(() => {
                            setPending(false);
                        });
                }}
                type="button"
            >
                {pending ? "Requesting…" : "Resend verification email"}
            </button>
            {message ? (
                <p className="text-sm text-stone-600" role="status">
                    {message}
                </p>
            ) : null}
        </div>
    );
}

export function AccountLogoutButton() {
    const { clearSessionCache, me, refresh } = useAuth();
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    return (
        <div className="space-y-2">
            <ErrorNotice message={error} />
            <button
                className="comment-action"
                disabled={pending || !me?.csrf_token}
                onClick={() => {
                    if (!me?.csrf_token || pending) {
                        return;
                    }
                    setPending(true);
                    setError(null);
                    void authMutation(authApiPaths.logout, {}, me.csrf_token)
                        .then(() => {
                            clearSessionCache();
                            window.location.assign("/");
                        })
                        .catch(async (caught: unknown) => {
                            setError(requestError(caught).message);
                            if (
                                caught instanceof AuthApiError &&
                                caught.status === 403
                            ) {
                                await refresh();
                            }
                        })
                        .finally(() => {
                            setPending(false);
                        });
                }}
                type="button"
            >
                {pending ? "Logging out…" : "Logout"}
            </button>
        </div>
    );
}
