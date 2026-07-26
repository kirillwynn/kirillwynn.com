import { cookies, draftMode } from "next/headers";
import { NextResponse } from "next/server";

import { enterDraftMode } from "@/lib/draft-entry";
import { previewTtlSeconds } from "@/lib/server/config";
import { resolvePreview } from "@/lib/server/django";
import {
    PREVIEW_ENTRY_COOKIE,
    PREVIEW_SNAPSHOT_COOKIE,
} from "@/lib/server/preview-cookies";

export async function GET(request: Request) {
    const draft = await draftMode();
    const cookieStore = await cookies();
    const entryCredential = cookieStore.get(PREVIEW_ENTRY_COOKIE)?.value;
    const result = await enterDraftMode(entryCredential, resolvePreview, () => {
        draft.enable();
    });

    if (!result.ok) {
        return new NextResponse("Preview is unavailable.", {
            status: 404,
            headers: { "Cache-Control": "private, no-store" },
        });
    }

    const response = NextResponse.redirect(
        new URL(result.path, request.url),
        303,
    );
    response.cookies.set(PREVIEW_SNAPSHOT_COOKIE, result.credential, {
        httpOnly: true,
        sameSite: "lax",
        secure: new URL(request.url).protocol === "https:",
        maxAge: previewTtlSeconds(),
        path: "/posts",
    });
    response.cookies.set(PREVIEW_ENTRY_COOKIE, "", {
        httpOnly: true,
        sameSite: "lax",
        secure: new URL(request.url).protocol === "https:",
        maxAge: 0,
        expires: new Date(0),
        path: "/api/draft",
    });
    response.headers.set("Cache-Control", "private, no-store");
    return response;
}
