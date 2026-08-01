import type { Metadata } from "next";

import { EmailVerificationAction } from "@/components/account-credential-action";

export const metadata: Metadata = {
    title: "Verify email",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function VerifyEmailPage() {
    return (
        <section className="account-page" aria-labelledby="verify-email-title">
            <p className="eyebrow">Account security</p>
            <h1 id="verify-email-title" className="account-title">
                Verify email
            </h1>
            <p className="account-intro">
                The credential is removed from the address bar before it is
                submitted.
            </p>
            <EmailVerificationAction />
        </section>
    );
}
