import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import process from "node:process";

const standaloneDirectory = process.argv[2] ?? "frontend/next/.next/standalone";
const server = `${standaloneDirectory}/server.js`;
const origins = [
    ["https://staging.kirillwynn.com", "3211"],
    ["https://kirillwynn.com", "3212"],
];

async function waitFor(url, child, stderr) {
    for (let attempt = 0; attempt < 50; attempt += 1) {
        if (child.exitCode !== null) {
            throw new Error(
                `standalone server exited with ${child.exitCode}: ${stderr()}`,
            );
        }
        try {
            const response = await fetch(url);
            if (response.ok) return response.text();
        } catch {}
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`standalone server did not become ready at ${url}`);
}

for (const [origin, port] of origins) {
    const child = spawn(process.execPath, [server], {
        env: {
            ...process.env,
            NODE_ENV: "production",
            HOSTNAME: "127.0.0.1",
            PORT: port,
            PUBLIC_SITE_URL: origin,
            DJANGO_API_URL: "http://127.0.0.1:9",
            REVALIDATION_SECRET: "runtime-origin-check-secret-32-bytes",
        },
        stdio: ["ignore", "pipe", "pipe"],
    });
    let childStderr = "";
    child.stderr.on("data", (chunk) => {
        childStderr = `${childStderr}${chunk}`.slice(-4000);
    });
    try {
        const health = await waitFor(
            `http://127.0.0.1:${port}/internal/health`,
            child,
            () => childStderr,
        );
        if (!health.includes('"status":"ok"')) {
            throw new Error(`unexpected health payload for ${origin}`);
        }
    } finally {
        if (child.exitCode === null) {
            const exited = new Promise((resolve) =>
                child.once("exit", resolve),
            );
            child.kill("SIGTERM");
            await exited;
        }
    }
}

const staticManifest = await readFile(
    "frontend/next/.next/routes-manifest.json",
    "utf8",
);
if (!staticManifest.includes("http://django:8000")) {
    throw new Error(
        "standalone rewrites do not use the environment-neutral Django alias",
    );
}
if (staticManifest.includes("http://localhost:8000")) {
    throw new Error("local Django origin was embedded in standalone rewrites");
}
for (const [origin] of origins) {
    if (staticManifest.includes(origin)) {
        throw new Error(
            `runtime origin was embedded in build metadata: ${origin}`,
        );
    }
}
