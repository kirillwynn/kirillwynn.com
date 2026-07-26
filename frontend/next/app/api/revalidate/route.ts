import { revalidatePath, revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

import {
    revalidationSecret,
    revalidationWindowSeconds,
} from "@/lib/server/config";
import {
    authenticateRevalidation,
    markRevalidationDelivered,
} from "@/lib/server/revalidation";

export async function POST(request: Request) {
    const body = await request.text();
    const result = authenticateRevalidation({
        body,
        timestamp: request.headers.get("x-revalidation-timestamp"),
        signature: request.headers.get("x-revalidation-signature"),
        secret: revalidationSecret(),
        windowSeconds: revalidationWindowSeconds(),
    });

    if (!result.ok) {
        return NextResponse.json(
            { detail: "Invalid revalidation request." },
            { status: 401 },
        );
    }
    if (!result.duplicate) {
        for (const tag of result.invalidations.tags) {
            revalidateTag(tag, "max");
        }
        for (const path of result.invalidations.paths) {
            revalidatePath(path);
        }
        markRevalidationDelivered(result.event.event_id);
    }
    return NextResponse.json({
        event_id: result.event.event_id,
        duplicate: result.duplicate,
    });
}
