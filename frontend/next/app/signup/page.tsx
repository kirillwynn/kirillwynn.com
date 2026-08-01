import type { Metadata } from "next";

import { SignupForm } from "@/components/local-auth-forms";

export const metadata: Metadata = {
    title: "Create account",
    robots: { index: false, follow: false },
};

export default async function SignupPage({
    searchParams,
}: {
    searchParams: Promise<{ next?: string }>;
}) {
    const params = await searchParams;
    return (
        <section className="account-page" aria-labelledby="signup-title">
            <p className="eyebrow">Account</p>
            <h1 id="signup-title" className="account-title">
                Create account
            </h1>
            <p className="account-intro">
                Your email stays private. Your nickname is the public name shown
                with posts, comments and reactions.
            </p>
            <div className="account-card">
                <SignupForm next={params.next} />
            </div>
        </section>
    );
}
