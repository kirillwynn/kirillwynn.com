import { draftMode } from "next/headers";
import { NextResponse } from "next/server";

import { previewCookieSecure } from "@/lib/server/config";
import {
    PREVIEW_ENTRY_COOKIE,
    PREVIEW_SNAPSHOT_COOKIE,
} from "@/lib/server/preview-cookies";

export async function GET(request: Request) {
    const draft = await draftMode();
    draft.disable();

    const response = NextResponse.redirect(new URL("/", request.url), 303);
    const secure = previewCookieSecure();
    response.cookies.set(PREVIEW_SNAPSHOT_COOKIE, "", {
        httpOnly: true,
        sameSite: "lax",
        secure,
        maxAge: 0,
        expires: new Date(0),
        path: "/posts",
    });
    response.cookies.set(PREVIEW_ENTRY_COOKIE, "", {
        httpOnly: true,
        sameSite: "lax",
        secure,
        maxAge: 0,
        expires: new Date(0),
        path: "/api/draft",
    });
    response.headers.set("Cache-Control", "private, no-store");
    return response;
}
