import type { Metadata } from "next";
import { Suspense } from "react";

import { ProfileRouteForm } from "@/components/auth-route-panels";

export const metadata: Metadata = {
    title: "Public profile",
    robots: { index: false, follow: false },
};

export default function ProfilePage() {
    return (
        <section className="account-page" aria-labelledby="profile-title">
            <p className="eyebrow">Account</p>
            <h1 id="profile-title" className="account-title">
                Public profile
            </h1>
            <p className="account-intro">
                Nicknames are unique. After your first confirmed change, another
                change is available in 30 days.
            </p>
            <div className="account-card">
                <Suspense fallback={null}>
                    <ProfileRouteForm />
                </Suspense>
            </div>
        </section>
    );
}
