"use client";

import { type FormEvent, useState } from "react";

import { useAuth } from "@/components/auth-provider";

type SubmissionState = "idle" | "pending" | "success" | "error" | "rate-limit";

export function SubscriptionForm({ compact = false }: { compact?: boolean }) {
    const { me, status: authStatus } = useAuth();
    const [email, setEmail] = useState("");
    const [submission, setSubmission] = useState<SubmissionState>("idle");

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!me?.csrf_token || submission === "pending") {
            setSubmission("error");
            return;
        }
        setSubmission("pending");
        try {
            const response = await fetch("/api/v1/subscriptions/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRFToken": me.csrf_token,
                },
                body: JSON.stringify({ email }),
            });
            if (response.status === 429) {
                setSubmission("rate-limit");
                return;
            }
            if (!response.ok) {
                setSubmission("error");
                return;
            }
            setEmail("");
            setSubmission("success");
        } catch {
            setSubmission("error");
        }
    }

    const unavailable = authStatus !== "ready" || !me?.csrf_token;
    return (
        <section
            className={`subscription-panel ${
                compact ? "subscription-panel-post" : "subscription-panel-feed"
            }`}
            aria-labelledby={
                compact ? "post-subscribe-title" : "feed-subscribe-title"
            }
        >
            <h2 id={compact ? "post-subscribe-title" : "feed-subscribe-title"}>
                Get new posts by email
            </h2>
            <p>
                One email per new publication. Confirm your address before the
                subscription starts, and unsubscribe anytime.
            </p>
            <form
                className="subscription-form"
                onSubmit={(event) => void submit(event)}
            >
                <div className="subscription-field">
                    <label
                        htmlFor={
                            compact
                                ? "post-subscription-email"
                                : "feed-subscription-email"
                        }
                    >
                        Email address
                    </label>
                    <input
                        id={
                            compact
                                ? "post-subscription-email"
                                : "feed-subscription-email"
                        }
                        className="feed-search-input"
                        type="email"
                        name="email"
                        autoComplete="email"
                        maxLength={320}
                        required
                        value={email}
                        onChange={(event) => {
                            setEmail(event.target.value);
                            if (submission !== "pending") {
                                setSubmission("idle");
                            }
                        }}
                        disabled={submission === "pending"}
                    />
                </div>
                <button
                    className="button-link button-link-primary shrink-0 disabled:cursor-not-allowed disabled:opacity-60"
                    type="submit"
                    disabled={unavailable || submission === "pending"}
                >
                    {submission === "pending" ? "Sending…" : "Subscribe"}
                </button>
            </form>
            <p className="subscription-status" role="status" aria-live="polite">
                {submission === "success"
                    ? "Check your inbox. If the address can be subscribed, a confirmation email is on its way."
                    : submission === "rate-limit"
                      ? "Too many attempts. Please wait before trying again."
                      : submission === "error"
                        ? "The request could not be completed. Please try again later."
                        : unavailable
                          ? "Preparing the secure form…"
                          : ""}
            </p>
        </section>
    );
}
