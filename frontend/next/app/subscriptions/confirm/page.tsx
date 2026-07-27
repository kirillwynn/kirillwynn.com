import type { Metadata } from "next";

import { SubscriptionCredentialAction } from "@/components/subscription-credential-action";

export const metadata: Metadata = {
    title: "Confirm subscription",
    robots: { index: false, follow: false },
    referrer: "no-referrer",
};

export default function ConfirmSubscriptionPage() {
    return <SubscriptionCredentialAction kind="confirm" />;
}
