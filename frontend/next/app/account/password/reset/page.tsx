import type { Metadata } from "next";

import { PasswordResetRequestForm } from "@/components/local-auth-forms";

export const metadata: Metadata = {
    title: "Reset password",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function PasswordResetPage() {
    return (
        <section
            className="account-page"
            aria-labelledby="password-reset-title"
        >
            <p className="eyebrow">Account security</p>
            <h1 id="password-reset-title" className="account-title">
                Reset password
            </h1>
            <p className="account-intro">
                The response is the same whether or not an eligible account
                exists.
            </p>
            <div className="account-card">
                <PasswordResetRequestForm />
            </div>
        </section>
    );
}
