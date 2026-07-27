import type { Metadata } from "next";

import { SubscriptionCredentialAction } from "@/components/subscription-credential-action";

export const metadata: Metadata = {
    title: "Unsubscribe",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function UnsubscribePage() {
    return <SubscriptionCredentialAction kind="unsubscribe" />;
}
