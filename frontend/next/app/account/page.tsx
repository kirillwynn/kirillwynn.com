import type { Metadata } from "next";
import { Suspense } from "react";

import { AccountRoutePanel } from "@/components/auth-route-panels";

export const metadata: Metadata = {
    title: "Account",
    robots: { index: false, follow: false },
};

export default function AccountPage() {
    return (
        <section className="mx-auto max-w-2xl">
            <p className="eyebrow">Account</p>
            <h1 className="mt-2 mb-6 text-3xl font-bold tracking-tight text-stone-950">
                Your account
            </h1>
            <Suspense fallback={null}>
                <AccountRoutePanel />
            </Suspense>
        </section>
    );
}
