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
    cacheComponents: true,
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
                source: "/api/auth/signup/",
                destination: `${django}/api/auth/signup/`,
            },
            {
                source: "/api/auth/login/",
                destination: `${django}/api/auth/login/`,
            },
            {
                source: "/api/auth/verify-email/",
                destination: `${django}/api/auth/verify-email/`,
            },
            {
                source: "/api/auth/verify-email/resend/",
                destination: `${django}/api/auth/verify-email/resend/`,
            },
            {
                source: "/api/auth/password/reset/",
                destination: `${django}/api/auth/password/reset/`,
            },
            {
                source: "/api/auth/password/reset/confirm/",
                destination: `${django}/api/auth/password/reset/confirm/`,
            },
            {
                source: "/api/auth/password/set/",
                destination: `${django}/api/auth/password/set/`,
            },
            {
                source: "/api/auth/password/change/",
                destination: `${django}/api/auth/password/change/`,
            },
            {
                source: "/api/auth/profile/",
                destination: `${django}/api/auth/profile/`,
            },
            {
                source: "/api/v1/auth/logout/",
                destination: `${django}/api/v1/auth/logout/`,
            },
            {
                source: "/api/v1/auth/signup/",
                destination: `${django}/api/v1/auth/signup/`,
            },
            {
                source: "/api/v1/auth/login/",
                destination: `${django}/api/v1/auth/login/`,
            },
            {
                source: "/api/v1/auth/verify-email/",
                destination: `${django}/api/v1/auth/verify-email/`,
            },
            {
                source: "/api/v1/auth/verify-email/resend/",
                destination: `${django}/api/v1/auth/verify-email/resend/`,
            },
            {
                source: "/api/v1/auth/password/reset/",
                destination: `${django}/api/v1/auth/password/reset/`,
            },
            {
                source: "/api/v1/auth/password/reset/confirm/",
                destination: `${django}/api/v1/auth/password/reset/confirm/`,
            },
            {
                source: "/api/v1/auth/password/set/",
                destination: `${django}/api/v1/auth/password/set/`,
            },
            {
                source: "/api/v1/auth/password/change/",
                destination: `${django}/api/v1/auth/password/change/`,
            },
            {
                source: "/api/v1/auth/profile/",
                destination: `${django}/api/v1/auth/profile/`,
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
                source: "/api/v1/posts/",
                destination: `${django}/api/v1/posts/`,
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
                source: "/api/v1/reactions/catalog/",
                destination: `${django}/api/v1/reactions/catalog/`,
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
                source: "/api/v1/posts/:slug/reactions/:reactionId/participants/",
                destination: `${django}/api/v1/posts/:slug/reactions/:reactionId/participants/`,
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
                source: "/api/v1/comments/:id/reactions/:reactionId/participants/",
                destination: `${django}/api/v1/comments/:id/reactions/:reactionId/participants/`,
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
