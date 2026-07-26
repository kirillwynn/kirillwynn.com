import type { NextConfig } from "next";
import { fileURLToPath } from "node:url";

function djangoProxyOrigin(): string {
    const value = (
        process.env.DJANGO_API_URL ?? "http://localhost:8000"
    ).replace(/\/$/, "");
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
        ]);
    },
    turbopack: {
        root: fileURLToPath(new URL(".", import.meta.url)),
    },
};

export default nextConfig;
