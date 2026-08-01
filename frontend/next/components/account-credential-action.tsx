"use client";

import {
    type FormEvent,
    useEffect,
    useId,
    useLayoutEffect,
    useRef,
    useState,
} from "react";

import { useAuth } from "@/components/auth-provider";
import { AuthApiError, authApiPaths, authMutation } from "@/lib/auth";

type CredentialState =
    | "loading"
    | "ready"
    | "pending"
    | "success"
    | "expired"
    | "used"
    | "unavailable"
    | "invalid"
    | "session-expired"
    | "rate-limited"
    | "network";

export function takeAccountCredentialFromFragment(): string | null {
    const raw = window.location.hash.slice(1);
    const parameters = new URLSearchParams(raw);
    const values = parameters.getAll("credential");
    const validShape =
        values.length === 1 &&
        Array.from(parameters.keys()).every((key) => key === "credential");
    window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}`,
    );
    return validShape && values[0] ? values[0] : null;
}

function classify(error: unknown): CredentialState {
    if (!(error instanceof AuthApiError)) {
        return "network";
    }
    if (error.code === "expired") {
        return "expired";
    }
    if (error.code === "used") {
        return "used";
    }
    if (error.code === "unavailable") {
        return "unavailable";
    }
    if (error.status === 403) {
        return "session-expired";
    }
    if (error.status === 429) {
        return "rate-limited";
    }
    if (error.status === 0 || error.status >= 500) {
        return "network";
    }
    return "invalid";
}

function CredentialFieldError({
    id,
    messages,
}: {
    id: string;
    messages: string[] | undefined;
}) {
    return messages?.length ? (
        <p className="account-field-error" id={id}>
            {messages[0]}
        </p>
    ) : null;
}

function stateMessage(
    kind: "verify" | "reset",
    state: CredentialState,
): string {
    const verification = kind === "verify";
    if (state === "loading") {
        return "Checking the secure link…";
    }
    if (state === "ready") {
        return verification
            ? "The link is ready to verify."
            : "Choose a new password to finish the reset.";
    }
    if (state === "pending") {
        return verification ? "Verifying email…" : "Changing password…";
    }
    if (state === "success") {
        return verification
            ? "Email verified. You can now use your account."
            : "Password reset. Other sessions are no longer valid.";
    }
    if (state === "expired") {
        return "This secure link has expired. Request a new email.";
    }
    if (state === "used") {
        return "This secure link has already been used.";
    }
    if (state === "unavailable") {
        return "This account is unavailable.";
    }
    if (state === "session-expired") {
        return "The browser security session expired. Reload the original email link.";
    }
    if (state === "network") {
        return "The account service could not be reached. You can retry without reopening the link.";
    }
    if (state === "rate-limited") {
        return "Too many attempts. Wait briefly, then retry without reopening the link.";
    }
    return "This secure link is invalid or has been replaced by a newer link.";
}

export function EmailVerificationAction() {
    const { me, refresh, status: authStatus } = useAuth();
    const credential = useRef<string | null>(null);
    const consumed = useRef(false);
    const started = useRef(false);
    const [state, setState] = useState<CredentialState>("loading");

    useLayoutEffect(() => {
        if (consumed.current) {
            return;
        }
        consumed.current = true;
        credential.current = takeAccountCredentialFromFragment();
        setState(credential.current ? "ready" : "invalid");
    }, []);

    async function verify() {
        if (!credential.current || !me?.csrf_token || started.current) {
            return;
        }
        started.current = true;
        setState("pending");
        try {
            await authMutation(
                authApiPaths.verifyEmail,
                { credential: credential.current },
                me.csrf_token,
            );
            credential.current = null;
            setState("success");
            await refresh();
        } catch (caught) {
            const next = classify(caught);
            if (next !== "network" && next !== "rate-limited") {
                credential.current = null;
            }
            setState(next);
        } finally {
            started.current = false;
        }
    }

    useEffect(() => {
        if (state === "ready" && authStatus === "ready") {
            void verify();
        } else if (state === "ready" && authStatus === "error") {
            setState("network");
        }
    }, [authStatus, state]);

    async function retry() {
        if (authStatus === "ready") {
            await verify();
            return;
        }
        setState("loading");
        const restored = await refresh();
        setState(restored ? "ready" : "network");
    }

    return (
        <div className="account-card space-y-5">
            <p aria-live="polite" role="status">
                {stateMessage("verify", state)}
            </p>
            {(state === "network" || state === "rate-limited") &&
            credential.current ? (
                <button
                    className="button-link"
                    onClick={() => {
                        void retry();
                    }}
                    type="button"
                >
                    Retry verification
                </button>
            ) : null}
            {state === "expired" || state === "invalid" ? (
                <a className="button-link" href="/account">
                    Request another verification email
                </a>
            ) : null}
            {state === "success" ? (
                <a
                    className="button-link"
                    href={me?.authenticated ? "/account" : "/login"}
                >
                    {me?.authenticated ? "Open account" : "Continue to login"}
                </a>
            ) : null}
        </div>
    );
}

export function PasswordResetConfirmationForm() {
    const { me, refresh, status: authStatus } = useAuth();
    const credential = useRef<string | null>(null);
    const consumed = useRef(false);
    const [state, setState] = useState<CredentialState>("loading");
    const [password, setPassword] = useState("");
    const [confirmation, setConfirmation] = useState("");
    const [message, setMessage] = useState<string | null>(null);
    const [fields, setFields] = useState<Partial<Record<string, string[]>>>({});
    const passwordErrorId = useId();
    const confirmationErrorId = useId();

    useLayoutEffect(() => {
        if (consumed.current) {
            return;
        }
        consumed.current = true;
        credential.current = takeAccountCredentialFromFragment();
        setState(credential.current ? "ready" : "invalid");
    }, []);

    useEffect(() => {
        if (state === "ready" && authStatus === "error") {
            setState("network");
        }
    }, [authStatus, state]);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!credential.current || !me?.csrf_token || state === "pending") {
            return;
        }
        setState("pending");
        setMessage(null);
        setFields({});
        try {
            await authMutation(
                authApiPaths.passwordResetConfirm,
                {
                    credential: credential.current,
                    password,
                    password_confirmation: confirmation,
                },
                me.csrf_token,
            );
            credential.current = null;
            setPassword("");
            setConfirmation("");
            setState("success");
        } catch (caught) {
            setPassword("");
            setConfirmation("");
            const validationFailure =
                caught instanceof AuthApiError &&
                caught.status === 400 &&
                caught.code === null &&
                Object.keys(caught.fields).length > 0;
            if (validationFailure) {
                setState("ready");
                setMessage(caught.message);
                setFields(caught.fields);
                return;
            }
            const next = classify(caught);
            if (next !== "network" && next !== "rate-limited") {
                credential.current = null;
            }
            setState(next);
            setMessage(null);
        }
    }

    async function retrySecuritySession() {
        setState("loading");
        const restored = await refresh();
        setState(restored ? "ready" : "network");
    }

    return (
        <div className="account-card space-y-5">
            <p
                aria-live="polite"
                role={state === "invalid" || message ? "alert" : "status"}
            >
                {message ?? stateMessage("reset", state)}
            </p>
            {state === "network" && authStatus === "error" ? (
                <button
                    className="button-link"
                    onClick={() => {
                        void retrySecuritySession();
                    }}
                    type="button"
                >
                    Retry secure session
                </button>
            ) : null}
            {authStatus === "ready" &&
            (state === "ready" ||
                state === "network" ||
                state === "rate-limited") ? (
                <form
                    className="account-form"
                    onSubmit={(event) => {
                        void submit(event);
                    }}
                >
                    <label className="account-field-group">
                        <span className="account-label">New password</span>
                        <input
                            aria-describedby={
                                fields.password ? passwordErrorId : undefined
                            }
                            aria-invalid={Boolean(fields.password)}
                            autoComplete="new-password"
                            className="account-input"
                            name="password"
                            onChange={(event) => {
                                setPassword(event.target.value);
                            }}
                            required
                            type="password"
                            value={password}
                        />
                        <CredentialFieldError
                            id={passwordErrorId}
                            messages={fields.password}
                        />
                    </label>
                    <label className="account-field-group">
                        <span className="account-label">
                            Confirm new password
                        </span>
                        <input
                            aria-describedby={
                                fields.password_confirmation
                                    ? confirmationErrorId
                                    : undefined
                            }
                            aria-invalid={Boolean(fields.password_confirmation)}
                            autoComplete="new-password"
                            className="account-input"
                            name="password_confirmation"
                            onChange={(event) => {
                                setConfirmation(event.target.value);
                            }}
                            required
                            type="password"
                            value={confirmation}
                        />
                        <CredentialFieldError
                            id={confirmationErrorId}
                            messages={fields.password_confirmation}
                        />
                    </label>
                    <button
                        className="button-link"
                        disabled={!me?.csrf_token}
                        type="submit"
                    >
                        Reset password
                    </button>
                </form>
            ) : null}
            {state === "pending" ? (
                <p role="status">Changing password…</p>
            ) : null}
            {state === "success" ? (
                <a className="button-link" href="/login">
                    Login with the new password
                </a>
            ) : null}
            {state === "expired" || state === "used" || state === "invalid" ? (
                <a className="button-link" href="/account/password/reset">
                    Request a new reset email
                </a>
            ) : null}
        </div>
    );
}
