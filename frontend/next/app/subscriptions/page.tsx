import type { Metadata } from "next";
import { draftMode } from "next/headers";
import { Suspense } from "react";

import { SubscriptionForm } from "@/components/subscription-form";

export const metadata: Metadata = {
    title: "Subscriptions",
    description: "Subscribe to new writing from Kirill Wynn.",
    alternates: { canonical: "/subscriptions/" },
};

async function SubscriptionContent() {
    const draft = await draftMode();
    return (
        <div className="state-page subscription-page">
            {draft.isEnabled ? (
                <section className="state-panel">
                    <p className="eyebrow">Draft Mode</p>
                    <h1>Subscriptions are unavailable in preview.</h1>
                    <p>Exit preview before changing a public subscription.</p>
                </section>
            ) : (
                <SubscriptionForm />
            )}
        </div>
    );
}

export default function SubscriptionsPage() {
    return (
        <Suspense fallback={<div className="state-page subscription-page" />}>
            <SubscriptionContent />
        </Suspense>
    );
}
