import type { Metadata } from "next";

import { LoginPanel } from "@/components/login-panel";

export const metadata: Metadata = {
    title: "Login",
    robots: { index: false, follow: false },
};

export default async function LoginPage({
    searchParams,
}: {
    searchParams: Promise<{ error?: string; next?: string }>;
}) {
    const params = await searchParams;
    return (
        <section className="mx-auto max-w-md">
            <p className="eyebrow">Account</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-stone-950">
                Login
            </h1>
            <p className="mt-3 mb-6 text-stone-600">
                Use a verified Google or GitHub identity. Provider access tokens
                are not retained.
            </p>
            <LoginPanel error={params.error} next={params.next} />
        </section>
    );
}
