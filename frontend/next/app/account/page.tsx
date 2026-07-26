import type { Metadata } from "next";

import { AccountPanel } from "@/components/account-panel";

export const metadata: Metadata = {
    title: "Account",
    robots: { index: false, follow: false },
};

export default async function AccountPage({
    searchParams,
}: {
    searchParams: Promise<{ error?: string }>;
}) {
    const params = await searchParams;
    return (
        <section className="mx-auto max-w-2xl">
            <p className="eyebrow">Account</p>
            <h1 className="mt-2 mb-6 text-3xl font-bold tracking-tight text-stone-950">
                Your account
            </h1>
            <AccountPanel error={params.error} />
        </section>
    );
}
