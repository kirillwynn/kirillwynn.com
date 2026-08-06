import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
    title: "Page not found",
    description: "The requested page could not be found.",
    robots: { index: false, follow: false },
};

export default function NotFound() {
    return (
        <section className="state-page">
            <div className="state-panel">
                <p className="eyebrow">404</p>
                <h1>Page not found</h1>
                <p>
                    The page may have moved, or it may never have been
                    published.
                </p>
                <Link className="button-link" href="/">
                    Return to Feed
                </Link>
            </div>
        </section>
    );
}
