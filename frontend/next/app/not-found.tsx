import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Page not found",
    description: "The requested page could not be found.",
    robots: { index: false, follow: false },
};

export default function NotFound() {
    return (
        <section className="mx-auto max-w-xl py-12 text-center">
            <p className="eyebrow">404</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-stone-950">
                Page not found
            </h1>
            <p className="mt-4 leading-7 text-stone-600">
                The page may have moved, or it may never have been published.
            </p>
            <a className="button-link mt-7" href="/">
                Return to Feed
            </a>
        </section>
    );
}
