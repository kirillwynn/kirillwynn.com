import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { publicSiteUrl } from "@/lib/server/config";

import "./globals.css";

export const metadata: Metadata = {
    metadataBase: new URL(publicSiteUrl()),
    title: {
        default: "Kirill Wynn",
        template: "%s · Kirill Wynn",
    },
    description:
        "Personal writing by Kirill Wynn about software, systems, and building things.",
    alternates: { canonical: "/" },
    openGraph: {
        type: "website",
        siteName: "Kirill Wynn",
        title: "Kirill Wynn",
        description:
            "Personal writing about software, systems, and building things.",
        url: "/",
    },
};

export default function RootLayout({
    children,
}: Readonly<{ children: ReactNode }>) {
    return (
        <html lang="en">
            <body className="flex min-h-dvh flex-col bg-stone-50 text-stone-900 antialiased">
                <a className="skip-link" href="#main-content">
                    Skip to content
                </a>
                <AuthProvider>
                    <SiteHeader />
                    <main
                        id="main-content"
                        className="site-container w-full flex-1 py-10 sm:py-14"
                    >
                        {children}
                    </main>
                    <SiteFooter />
                </AuthProvider>
            </body>
        </html>
    );
}
