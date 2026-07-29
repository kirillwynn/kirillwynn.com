import type { NextConfig } from "next";
import { fileURLToPath } from "node:url";

function djangoProxyOrigin(): string {
    // Rewrites are compiled into the standalone server. The Compose service
    // alias is intentionally identical in staging and production; local
    // non-Compose development overrides it through .env.local.
    const value = (process.env.DJANGO_API_URL ?? "http://django:8000").replace(
        /\/$/,
        "",
    );
    const url = new URL(value);
    if (
        !["http:", "https:"].includes(url.protocol) ||
        url.username ||
        url.password ||
        url.pathname !== "/" ||
        url.search ||
        url.hash
    ) {
        throw new Error("DJANGO_API_URL must be an HTTP(S) origin");
    }
    return url.origin;
}

const nextConfig: NextConfig = {
    output: "standalone",
    skipTrailingSlashRedirect: true,
    rewrites() {
        const django = djangoProxyOrigin();
        return Promise.resolve([
            {
                source: "/accounts/:path*/",
                destination: `${django}/accounts/:path*/`,
            },
            {
                source: "/accounts/:path*",
                destination: `${django}/accounts/:path*`,
            },
            {
                source: "/api/me/",
                destination: `${django}/api/me/`,
            },
            {
                source: "/api/auth/logout/",
                destination: `${django}/api/auth/logout/`,
            },
            {
                source: "/api/v1/subscriptions/",
                destination: `${django}/api/v1/subscriptions/`,
            },
            {
                source: "/api/v1/subscriptions/confirm/",
                destination: `${django}/api/v1/subscriptions/confirm/`,
            },
            {
                source: "/api/v1/subscriptions/unsubscribe/",
                destination: `${django}/api/v1/subscriptions/unsubscribe/`,
            },
            {
                source: "/api/v1/subscriptions/unsubscribe/one-click/",
                destination: `${django}/api/v1/subscriptions/unsubscribe/one-click/`,
            },
            {
                source: "/api/v1/email/webhooks/resend/",
                destination: `${django}/api/v1/email/webhooks/resend/`,
            },
            {
                source: "/api/v1/posts/:slug/comments/",
                destination: `${django}/api/v1/posts/:slug/comments/`,
            },
            {
                source: "/api/v1/reactions/config/",
                destination: `${django}/api/v1/reactions/config/`,
            },
            {
                source: "/api/v1/reactions/posts/",
                destination: `${django}/api/v1/reactions/posts/`,
            },
            {
                source: "/api/v1/posts/:slug/reactions/",
                destination: `${django}/api/v1/posts/:slug/reactions/`,
            },
            {
                source: "/api/v1/posts/:slug/reactions/toggle/",
                destination: `${django}/api/v1/posts/:slug/reactions/toggle/`,
            },
            {
                source: "/api/v1/posts/:slug/reactions/:emoji/participants/",
                destination: `${django}/api/v1/posts/:slug/reactions/:emoji/participants/`,
            },
            {
                source: "/api/v1/comments/:id/reactions/",
                destination: `${django}/api/v1/comments/:id/reactions/`,
            },
            {
                source: "/api/v1/comments/:id/reactions/toggle/",
                destination: `${django}/api/v1/comments/:id/reactions/toggle/`,
            },
            {
                source: "/api/v1/comments/:id/reactions/:emoji/participants/",
                destination: `${django}/api/v1/comments/:id/reactions/:emoji/participants/`,
            },
            {
                source: "/api/v1/comments/:id/thread/",
                destination: `${django}/api/v1/comments/:id/thread/`,
            },
            {
                source: "/api/v1/comments/:id/replies/",
                destination: `${django}/api/v1/comments/:id/replies/`,
            },
            {
                source: "/api/v1/comments/:id/",
                destination: `${django}/api/v1/comments/:id/`,
            },
        ]);
    },
    turbopack: {
        root: fileURLToPath(new URL(".", import.meta.url)),
    },
};

export default nextConfig;
