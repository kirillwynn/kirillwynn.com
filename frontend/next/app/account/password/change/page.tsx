import type { Metadata } from "next";

import { AccountPasswordForm } from "@/components/local-auth-forms";

export const metadata: Metadata = {
    title: "Change password",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function PasswordChangePage() {
    return (
        <section
            className="account-page"
            aria-labelledby="password-change-title"
        >
            <p className="eyebrow">Account security</p>
            <h1 id="password-change-title" className="account-title">
                Change password
            </h1>
            <p className="account-intro">
                A successful change keeps this browser signed in and invalidates
                other sessions.
            </p>
            <div className="account-card">
                <AccountPasswordForm mode="change" />
            </div>
        </section>
    );
}
