import type { Metadata } from "next";

import { AccountPasswordForm } from "@/components/local-auth-forms";

export const metadata: Metadata = {
    title: "Set password",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function PasswordSetPage() {
    return (
        <section className="account-page" aria-labelledby="password-set-title">
            <p className="eyebrow">Account security</p>
            <h1 id="password-set-title" className="account-title">
                Set password
            </h1>
            <p className="account-intro">
                Add email-and-password login without disconnecting Google or
                GitHub.
            </p>
            <div className="account-card">
                <AccountPasswordForm mode="set" />
            </div>
        </section>
    );
}
