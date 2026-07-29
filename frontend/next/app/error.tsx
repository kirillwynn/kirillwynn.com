"use client";

import { useEffect } from "react";

export default function ErrorPage({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error(error);
    }, [error]);

    return (
        <section className="state-page">
            <div className="state-panel">
                <p className="eyebrow">Service unavailable</p>
                <h1>The content service did not respond.</h1>
                <p>
                    This is a temporary upstream problem, not a missing page.
                    Please try again.
                </p>
                <button
                    className="button-link button-link-primary"
                    type="button"
                    onClick={reset}
                >
                    Try again
                </button>
            </div>
        </section>
    );
}
