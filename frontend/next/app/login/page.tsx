import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginRoutePanel } from "@/components/auth-route-panels";

export const metadata: Metadata = {
    title: "Login",
    robots: { index: false, follow: false },
};

export default function LoginPage() {
    return (
        <section className="mx-auto max-w-md">
            <p className="eyebrow">Account</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-stone-950">
                Login
            </h1>
            <p className="mt-3 mb-6 text-stone-600">
                Use email and password, or continue with Google or GitHub.
                Provider access tokens are not retained.
            </p>
            <Suspense fallback={null}>
                <LoginRoutePanel />
            </Suspense>
        </section>
    );
}
