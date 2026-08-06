import type { Metadata } from "next";
import { draftMode } from "next/headers";
import { connection } from "next/server";
import { type ReactNode, Suspense } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { PreviewBanner } from "@/components/preview-banner";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader, SiteHeaderFallback } from "@/components/site-header";
import { publicSiteUrl } from "@/lib/server/config";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
    await connection();
    return {
        metadataBase: new URL(publicSiteUrl()),
        title: {
            default: "Kirill Wynn",
            template: "%s · Kirill Wynn",
        },
        description: "Personal writing by Kirill Wynn.",
        alternates: { canonical: "/" },
        openGraph: {
            type: "website",
            siteName: "Kirill Wynn",
            title: "Kirill Wynn",
            description: "Personal writing by Kirill Wynn.",
            url: "/",
        },
    };
}

async function DraftPreviewSlot() {
    await connection();
    const draft = await draftMode();
    return draft.isEnabled ? (
        <div className="site-container preview-container">
            <PreviewBanner />
        </div>
    ) : null;
}

export default function RootLayout({
    children,
}: Readonly<{ children: ReactNode }>) {
    return (
        <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
            <head>
                <script
                    id="theme-init"
                    dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }}
                />
            </head>
            <body className="flex min-h-dvh flex-col antialiased">
                <a className="skip-link" href="#main-content">
                    Skip to content
                </a>
                <AuthProvider>
                    <Suspense fallback={<SiteHeaderFallback />}>
                        <SiteHeader />
                    </Suspense>
                    <Suspense fallback={null}>
                        <DraftPreviewSlot />
                    </Suspense>
                    <main
                        id="main-content"
                        className="site-container site-main"
                        tabIndex={-1}
                    >
                        {children}
                    </main>
                    <SiteFooter />
                </AuthProvider>
            </body>
        </html>
    );
}
