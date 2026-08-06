import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const frontendRoot = path.resolve(process.argv[2] ?? "frontend/next");
const appRoot = path.join(frontendRoot, ".next", "server", "app");
const staticRoot = path.join(frontendRoot, ".next", "static", "chunks");
const entryDocuments = [
    path.join(appRoot, "index.html"),
    path.join(appRoot, "posts", "[slug].html"),
];
const resultMarker = '"Reaction results"';
const initialChunks = new Set();

for (const documentPath of entryDocuments) {
    const html = await readFile(documentPath, "utf8");
    if (
        html.includes("/api/v1/reactions/catalog/") ||
        html.includes("/media/reactions/")
    ) {
        throw new Error(
            `reaction catalog data or assets leaked into ${documentPath}`,
        );
    }
    for (const match of html.matchAll(/<script[^>]+src="([^"]+)"/g)) {
        const source = match[1];
        if (!source?.startsWith("/_next/static/chunks/")) {
            continue;
        }
        initialChunks.add(path.basename(source));
    }
}

for (const filename of initialChunks) {
    const contents = await readFile(path.join(staticRoot, filename), "utf8");
    if (contents.includes(resultMarker)) {
        throw new Error(
            `lazy reaction picker results leaked into initial chunk ${filename}`,
        );
    }
}

const lazyChunks = [];
for (const filename of await readdir(staticRoot)) {
    if (!filename.endsWith(".js") || initialChunks.has(filename)) {
        continue;
    }
    const contents = await readFile(path.join(staticRoot, filename), "utf8");
    if (contents.includes(resultMarker)) {
        lazyChunks.push({ filename, size: Buffer.byteLength(contents) });
    }
}
if (lazyChunks.length === 0) {
    throw new Error("the reaction picker results were not emitted as a lazy chunk");
}
if (lazyChunks.some(({ size }) => size > 64 * 1024)) {
    throw new Error("a reaction picker results chunk exceeded 64 KiB");
}

process.stdout.write(
    `${JSON.stringify({ initial_chunks: initialChunks.size, lazy_chunks: lazyChunks })}\n`,
);
