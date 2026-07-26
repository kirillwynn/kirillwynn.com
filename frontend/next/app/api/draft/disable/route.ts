import { draftMode } from "next/headers";
import { NextResponse } from "next/server";

import {
    PREVIEW_ENTRY_COOKIE,
    PREVIEW_SNAPSHOT_COOKIE,
} from "@/lib/server/preview-cookies";

export async function GET(request: Request) {
    const draft = await draftMode();
    draft.disable();

    const response = NextResponse.redirect(new URL("/", request.url), 303);
    response.cookies.set(PREVIEW_SNAPSHOT_COOKIE, "", {
        maxAge: 0,
        expires: new Date(0),
        path: "/posts",
    });
    response.cookies.set(PREVIEW_ENTRY_COOKIE, "", {
        maxAge: 0,
        expires: new Date(0),
        path: "/api/draft",
    });
    response.headers.set("Cache-Control", "private, no-store");
    return response;
}
