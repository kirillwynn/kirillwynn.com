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
        <section className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-white p-8">
            <p className="eyebrow text-red-700">Service unavailable</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-950">
                The content service did not respond.
            </h1>
            <p className="mt-4 leading-7 text-stone-600">
                This is a temporary upstream problem, not a missing page. Please
                try again.
            </p>
            <button className="button-link mt-6" type="button" onClick={reset}>
                Try again
            </button>
        </section>
    );
}
