"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";

type ActionKind = "confirm" | "unsubscribe";
type ActionState =
    | "loading"
    | "ready"
    | "pending"
    | "success"
    | "already"
    | "invalid"
    | "infrastructure";

function takeCredentialFromFragment(): string | null {
    const parameters = new URLSearchParams(window.location.hash.slice(1));
    const credential = parameters.get("credential");
    window.history.replaceState(null, "", window.location.pathname);
    return credential;
}

export function SubscriptionCredentialAction({ kind }: { kind: ActionKind }) {
    const { me, status: authStatus } = useAuth();
    const [credential, setCredential] = useState<string | null>(null);
    const [state, setState] = useState<ActionState>("loading");

    useEffect(() => {
        const value = takeCredentialFromFragment();
        setCredential(value);
        setState(value ? "ready" : "invalid");
    }, []);

    async function submit() {
        if (!credential || !me?.csrf_token) {
            setState(authStatus === "ready" ? "invalid" : "infrastructure");
            return;
        }
        setState("pending");
        try {
            const endpoint =
                kind === "confirm"
                    ? "/api/v1/subscriptions/confirm/"
                    : "/api/v1/subscriptions/unsubscribe/";
            const response = await fetch(endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": me.csrf_token,
                },
                body: JSON.stringify({ credential }),
            });
            if (response.status === 400) {
                setState("invalid");
                setCredential(null);
                return;
            }
            if (!response.ok) {
                setState("infrastructure");
                return;
            }
            const payload = (await response.json()) as { status?: unknown };
            const already =
                payload.status === "already_confirmed" ||
                payload.status === "already_unsubscribed";
            setState(already ? "already" : "success");
            setCredential(null);
        } catch {
            setState("infrastructure");
        }
    }

    const confirmation = kind === "confirm";
    const title = confirmation ? "Confirm subscription" : "Unsubscribe";
    let message = confirmation
        ? "Choose Confirm to start receiving new posts."
        : "Choose Unsubscribe to stop future publication emails.";
    if (state === "success") {
        message = confirmation
            ? "Your subscription is confirmed."
            : "You have been unsubscribed.";
    } else if (state === "already") {
        message = confirmation
            ? "This subscription was already confirmed."
            : "This subscription was already unsubscribed.";
    } else if (state === "invalid") {
        message =
            "This link is invalid, expired, or has been replaced by a newer link.";
    } else if (state === "infrastructure") {
        message = "The request could not be completed. Please try again later.";
    } else if (state === "loading") {
        message = "Checking the link…";
    }

    return (
        <section
            className="mx-auto max-w-xl rounded-2xl border border-stone-200 bg-[var(--color-surface)] p-7 shadow-sm sm:p-10"
            aria-labelledby="subscription-action-title"
        >
            <p className="eyebrow">Email subscription</p>
            <h1
                id="subscription-action-title"
                className="mt-3 text-3xl font-semibold tracking-tight text-stone-950"
            >
                {title}
            </h1>
            <p
                className="mt-4 leading-7 text-stone-600"
                role="status"
                aria-live="polite"
            >
                {message}
            </p>
            {state === "ready" ||
            state === "pending" ||
            state === "infrastructure" ? (
                <button
                    className="button-link mt-6 disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onClick={() => void submit()}
                    disabled={state === "pending" || authStatus !== "ready"}
                >
                    {state === "pending"
                        ? "Working…"
                        : confirmation
                          ? "Confirm subscription"
                          : "Unsubscribe"}
                </button>
            ) : null}
        </section>
    );
}
