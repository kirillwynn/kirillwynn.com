import { Buffer } from "node:buffer";
import { createServer } from "node:http";
import { URL, URLSearchParams } from "node:url";

const host = "127.0.0.1";
const port = 3101;
const publishedAt = "2026-07-28T12:00:00Z";

let state;

function reset() {
    state = {
        nextCommentId: 20,
        postReactionCount: 1,
        comments: [
            comment({
                id: 10,
                body: "Welcome to the deterministic thread.",
                author: {
                    id: 7,
                    display_name: "Site Author",
                    is_site_author: true,
                },
                replyCount: 1,
            }),
        ],
        replies: [
            comment({
                id: 11,
                body: "A stable first reply.",
                kind: "reply",
                threadRootId: 10,
                replyTo: { id: 7, display_name: "Site Author" },
            }),
        ],
    };
}

function isAuthenticated(request) {
    return /(?:^|;\s*)e2e_provider=(google|github)(?:;|$)/.test(
        request.headers.cookie ?? "",
    );
}

function viewer(request, owner = false) {
    const authenticated = isAuthenticated(request);
    return {
        can_edit: authenticated && owner,
        can_delete: authenticated && owner,
        can_reply: authenticated,
        can_react: authenticated,
    };
}

function comment({
    id,
    body,
    kind = "comment",
    threadRootId = null,
    replyTo = null,
    author = {
        id: 2,
        display_name: "Mock Reader",
        is_site_author: false,
    },
    replyCount = 0,
}) {
    return {
        id,
        kind,
        body,
        status: "visible",
        author,
        thread_root_id: threadRootId,
        reply_to: replyTo,
        created_at: publishedAt,
        updated_at: publishedAt,
        edited_at: null,
        reply_count: replyCount,
        last_reply_at: replyCount ? publishedAt : null,
        reactions: [],
        viewer: {
            can_edit: false,
            can_delete: false,
            can_reply: false,
            can_react: false,
        },
    };
}

function post({ id, slug, title, excerpt, tags, body }) {
    return {
        api_version: "1.0",
        id,
        slug,
        title,
        excerpt,
        published_at: publishedAt,
        updated_at: publishedAt,
        tags,
        canonical_path: `/posts/${slug}`,
        canonical_url: `http://localhost:3100/posts/${slug}`,
        seo: { title, description: excerpt },
        open_graph: { title, description: excerpt, image: null },
        body: [
            {
                id: `body-${String(id)}`,
                type: "rich_text",
                value: { html: `<p>${body}</p>` },
            },
        ],
    };
}

const posts = [
    post({
        id: 1,
        slug: "testing-secure-systems",
        title: "Testing secure systems",
        excerpt: "A deterministic post for critical reader flows.",
        tags: [
            { name: "Django", slug: "django" },
            { name: "Security", slug: "security" },
        ],
        body: "Live content stays isolated from preview revisions.",
    }),
    post({
        id: 2,
        slug: "django-delivery-notes",
        title: "Django delivery notes",
        excerpt: "PostgreSQL, outboxes, and recovery checks.",
        tags: [{ name: "Django", slug: "django" }],
        body: "Delivery remains idempotent.",
    }),
];

const previewPost = post({
    id: 1,
    slug: "testing-secure-systems",
    title: "Draft: testing secure systems",
    excerpt: "An isolated unpublished revision.",
    tags: [{ name: "Security", slug: "security" }],
    body: "Only the credential-bound draft context can read this revision.",
});

function listItem(value) {
    const metadata = { ...value };
    delete metadata.body;
    return { ...metadata, lead_image: null };
}

function json(response, status, payload, headers = {}) {
    response.writeHead(status, {
        "Cache-Control": "private, no-store",
        "Content-Type": "application/json",
        ...headers,
    });
    response.end(JSON.stringify(payload));
}

async function body(request) {
    const chunks = [];
    for await (const chunk of request) {
        chunks.push(chunk);
    }
    return Buffer.concat(chunks).toString("utf8");
}

function withViewer(request, value) {
    const owner = value.author.id === 2;
    return { ...value, viewer: viewer(request, owner) };
}

const reactionCatalog = [
    {
        id: "pepeclap",
        name: "Pepe clap",
        label: "Clapping",
        kind: "animated",
        asset_url: "/media/reactions/pepeclap/hash/animation.gif",
        poster_url: "/media/reactions/pepeclap/hash/poster.webp",
        width: 64,
        height: 64,
        version: "sha256-clap",
    },
    {
        id: "pepehmm",
        name: "Pepe hmm",
        label: "Thinking",
        kind: "static",
        asset_url: "/media/reactions/pepehmm/hash/asset.webp",
        poster_url: "/media/reactions/pepehmm/hash/asset.webp",
        width: 64,
        height: 64,
        version: "sha256-hmm",
    },
    {
        id: "pepelove",
        name: "Pepe love",
        label: "Sending love",
        kind: "static",
        asset_url: "/media/reactions/pepelove/hash/asset.webp",
        poster_url: "/media/reactions/pepelove/hash/asset.webp",
        width: 64,
        height: 64,
        version: "sha256-love",
    },
];

function reactionGroup(request) {
    return {
        reaction: reactionCatalog[0],
        count: state.postReactionCount,
        viewer_reacted: isAuthenticated(request) && state.postReactionCount > 1,
        participants:
            "/api/v1/posts/testing-secure-systems/reactions/pepeclap/participants/",
    };
}

function safeReturnTo(value) {
    if (
        value === "/" ||
        value === "/bridge" ||
        value === "/account" ||
        /^\/posts\/[\p{L}\p{N}_-]+(?:\?thread=\d+)?$/u.test(value)
    ) {
        return value;
    }
    return "/";
}

reset();

createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", `http://${host}:${String(port)}`);
    const path = decodeURIComponent(url.pathname);

    if (path === "/__health") {
        json(response, 200, { ok: true });
        return;
    }
    if (path === "/__reset" && request.method === "POST") {
        reset();
        json(response, 200, { ok: true });
        return;
    }
    if (path === "/api/me/") {
        const authenticated = isAuthenticated(request);
        json(response, 200, {
            authenticated,
            user: authenticated
                ? {
                      id: 2,
                      display_name: "Mock Reader",
                      email: "reader@example.test",
                      is_admin: false,
                      is_banned: false,
                      can_interact: true,
                  }
                : null,
            providers: {
                google: {
                    available: true,
                    connected:
                        request.headers.cookie?.includes(
                            "e2e_provider=google",
                        ) ?? false,
                },
                github: {
                    available: true,
                    connected:
                        request.headers.cookie?.includes(
                            "e2e_provider=github",
                        ) ?? false,
                },
            },
            csrf_token: "deterministic-test-csrf",
        });
        return;
    }
    if (path === "/api/auth/logout/" && request.method === "POST") {
        response.writeHead(204, {
            "Cache-Control": "private, no-store",
            "Set-Cookie":
                "e2e_provider=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
        });
        response.end();
        return;
    }
    const login = path.match(/^\/accounts\/(google|github)\/login\/$/);
    if (login && request.method === "POST") {
        const fields = new URLSearchParams(await body(request));
        response.writeHead(303, {
            Location: safeReturnTo(fields.get("next") ?? "/"),
            "Set-Cookie": `e2e_provider=${login[1]}; Path=/; HttpOnly; SameSite=Lax`,
        });
        response.end();
        return;
    }
    if (path === "/api/v1/posts/" && request.method === "GET") {
        const query = url.searchParams.get("q")?.toLocaleLowerCase() ?? "";
        if (query === "force-upstream-error") {
            json(response, 503, { detail: "Deterministic upstream failure" });
            return;
        }
        const tag = url.searchParams.get("tag");
        const page = Number(url.searchParams.get("page") ?? "1");
        const filtered = posts.filter(
            (value) =>
                (!query ||
                    `${value.title} ${value.excerpt}`
                        .toLocaleLowerCase()
                        .includes(query)) &&
                (!tag || value.tags.some((item) => item.slug === tag)),
        );
        const pageResults =
            query || tag ? filtered : filtered.slice(page - 1, page);
        json(response, 200, {
            count: filtered.length,
            next:
                !query && !tag && page < filtered.length
                    ? `/api/v1/posts/?page=${String(page + 1)}`
                    : null,
            previous:
                !query && !tag && page > 1
                    ? `/api/v1/posts/?page=${String(page - 1)}`
                    : null,
            results: pageResults.map(listItem),
        });
        return;
    }
    if (path === "/api/v1/tags/" && request.method === "GET") {
        json(response, 200, {
            results: [
                { name: "Django", slug: "django", count: 2 },
                { name: "Security", slug: "security", count: 1 },
            ],
        });
        return;
    }
    if (path === "/api/v1/preview/resolve/" && request.method === "POST") {
        const payload = JSON.parse(await body(request));
        json(
            response,
            payload.credential === "e2e-preview" ? 200 : 404,
            payload.credential === "e2e-preview"
                ? previewPost
                : { detail: "Preview unavailable" },
        );
        return;
    }
    const postDetail = path.match(/^\/api\/v1\/posts\/([^/]+)\/$/);
    if (postDetail && request.method === "GET") {
        const found = posts.find((value) => value.slug === postDetail[1]);
        json(response, found ? 200 : 404, found ?? { detail: "Not found" });
        return;
    }
    if (path === "/api/v1/reactions/config/" && request.method === "GET") {
        json(response, 200, { quick_reactions: reactionCatalog });
        return;
    }
    if (path === "/api/v1/reactions/catalog/" && request.method === "GET") {
        json(response, 200, {
            version: "sha256-browser-contract",
            results: reactionCatalog,
        });
        return;
    }
    if (path === "/api/v1/reactions/posts/" && request.method === "GET") {
        const ids = (url.searchParams.get("ids") ?? "")
            .split(",")
            .map((value) => Number(value));
        json(response, 200, {
            results: ids
                .map((id) => posts.find((value) => value.id === id))
                .filter(Boolean)
                .map((value) => ({
                    post_id: value.id,
                    slug: value.slug,
                    reactions: value.id === 1 ? [reactionGroup(request)] : [],
                })),
        });
        return;
    }
    if (
        path === "/api/v1/posts/testing-secure-systems/reactions/" &&
        request.method === "GET"
    ) {
        json(response, 200, { reactions: [reactionGroup(request)] });
        return;
    }
    if (
        path === "/api/v1/posts/testing-secure-systems/reactions/toggle/" &&
        request.method === "POST"
    ) {
        const payload = JSON.parse(await body(request));
        if (
            Object.keys(payload).length !== 1 ||
            payload.reaction_id !== "pepeclap"
        ) {
            json(response, 400, { reaction_id: ["Unknown reaction ID."] });
            return;
        }
        state.postReactionCount = state.postReactionCount > 1 ? 1 : 2;
        json(response, 200, {
            action: state.postReactionCount > 1 ? "added" : "removed",
            reactions: [reactionGroup(request)],
        });
        return;
    }
    if (path.endsWith("/participants/") && request.method === "GET") {
        json(response, 200, {
            next: null,
            previous: null,
            results: [
                {
                    id: 7,
                    display_name: "Site Author",
                    is_site_author: true,
                },
            ],
        });
        return;
    }
    if (
        path === "/api/v1/posts/testing-secure-systems/comments/" &&
        request.method === "GET"
    ) {
        json(response, 200, {
            next: null,
            previous: null,
            results: state.comments.map((value) => withViewer(request, value)),
        });
        return;
    }
    if (
        path === "/api/v1/posts/testing-secure-systems/comments/" &&
        request.method === "POST"
    ) {
        const payload = JSON.parse(await body(request));
        const created = comment({
            id: state.nextCommentId++,
            body: String(payload.body).trim(),
        });
        state.comments.unshift(created);
        json(response, 201, withViewer(request, created));
        return;
    }
    const thread = path.match(/^\/api\/v1\/comments\/(\d+)\/thread\/$/);
    if (thread && request.method === "GET") {
        const root = state.comments.find(
            (value) => value.id === Number(thread[1]),
        );
        json(
            response,
            root ? 200 : 404,
            root
                ? {
                      root: withViewer(request, root),
                      next: null,
                      previous: null,
                      results: state.replies.map((value) =>
                          withViewer(request, value),
                      ),
                  }
                : { detail: "Not found" },
        );
        return;
    }
    const replies = path.match(/^\/api\/v1\/comments\/(\d+)\/replies\/$/);
    if (replies && request.method === "POST") {
        const payload = JSON.parse(await body(request));
        const rootId = Number(replies[1]);
        const created = comment({
            id: state.nextCommentId++,
            body: String(payload.body).trim(),
            kind: "reply",
            threadRootId: rootId,
            replyTo: { id: 7, display_name: "Site Author" },
        });
        state.replies.push(created);
        const root = state.comments.find((value) => value.id === rootId);
        if (root) {
            root.reply_count += 1;
            root.last_reply_at = publishedAt;
        }
        json(response, 201, withViewer(request, created));
        return;
    }
    if (
        /^\/api\/v1\/comments\/\d+\/reactions\/$/.test(path) &&
        request.method === "GET"
    ) {
        json(response, 200, { reactions: [] });
        return;
    }
    if (
        /^\/api\/v1\/comments\/\d+\/reactions\/toggle\/$/.test(path) &&
        request.method === "POST"
    ) {
        json(response, 200, { action: "added", reactions: [] });
        return;
    }
    if (path === "/api/v1/subscriptions/" && request.method === "POST") {
        json(response, 202, { status: "accepted" });
        return;
    }
    if (
        path === "/api/v1/subscriptions/confirm/" &&
        request.method === "POST"
    ) {
        json(response, 200, { status: "confirmed" });
        return;
    }
    if (
        path === "/api/v1/subscriptions/unsubscribe/" &&
        request.method === "POST"
    ) {
        json(response, 200, { status: "unsubscribed" });
        return;
    }

    json(response, 404, { detail: "Mock route not found" });
}).listen(port, host);
