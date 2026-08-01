import type { Metadata } from "next";

import { PasswordResetConfirmationForm } from "@/components/account-credential-action";

export const metadata: Metadata = {
    title: "Choose a new password",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function PasswordResetConfirmPage() {
    return (
        <section
            className="account-page"
            aria-labelledby="password-reset-confirm-title"
        >
            <p className="eyebrow">Account security</p>
            <h1 id="password-reset-confirm-title" className="account-title">
                Choose a new password
            </h1>
            <PasswordResetConfirmationForm />
        </section>
    );
}
