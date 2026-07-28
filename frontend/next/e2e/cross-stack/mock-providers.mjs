import { createServer } from "node:http";
import { URL } from "node:url";

const host = "127.0.0.1";
const port = 3202;

function json(response, payload) {
    response.writeHead(200, {
        "Cache-Control": "no-store",
        "Content-Type": "application/json",
    });
    response.end(JSON.stringify(payload));
}

createServer((request, response) => {
    const url = new URL(request.url ?? "/", `http://${host}:${String(port)}`);
    if (url.pathname === "/__health") {
        json(response, { ok: true });
        return;
    }
    if (
        url.pathname === "/google/authorize" ||
        url.pathname === "/github/login/oauth/authorize"
    ) {
        const destination = new URL(url.searchParams.get("redirect_uri"));
        destination.searchParams.set("code", "provider-boundary-code");
        destination.searchParams.set("state", url.searchParams.get("state"));
        response.writeHead(303, { Location: destination.toString() });
        response.end();
        return;
    }
    if (
        url.pathname === "/google/token" ||
        url.pathname === "/github/login/oauth/access_token"
    ) {
        json(response, {
            access_token: "provider-boundary-access-token",
            token_type: "bearer",
        });
        return;
    }
    if (url.pathname === "/google/userinfo") {
        json(response, {
            sub: "cross-stack-google",
            email: "reader@example.test",
            email_verified: true,
            name: "Cross Stack Reader",
        });
        return;
    }
    if (url.pathname === "/github/api/v3/user") {
        json(response, {
            id: 3202,
            login: "cross-stack-reader",
            name: "Cross Stack Reader",
            email: "reader@example.test",
        });
        return;
    }
    if (url.pathname === "/github/api/v3/user/emails") {
        json(response, [
            {
                email: "reader@example.test",
                primary: true,
                verified: true,
            },
        ]);
        return;
    }
    response.writeHead(404, {
        "Cache-Control": "no-store",
        "Content-Type": "application/json",
    });
    response.end(JSON.stringify({ detail: "provider mock route not found" }));
}).listen(port, host);
