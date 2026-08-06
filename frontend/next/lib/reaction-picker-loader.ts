import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/query-keys";
import { getReactionCatalog } from "@/lib/reactions";

let pickerModulePromise: Promise<
    typeof import("@/components/reaction-picker")
> | null = null;
let idlePreloadScheduled = false;

export function loadReactionPickerModule() {
    pickerModulePromise ??= import("@/components/reaction-picker");
    return pickerModulePromise;
}

function saveDataEnabled(): boolean {
    return Boolean(
        (
            navigator as Navigator & {
                connection?: { saveData?: boolean };
            }
        ).connection?.saveData,
    );
}

export function preloadReactionPickerResources(
    queryClient: QueryClient,
    mode: "idle" | "hover" | "intent",
): void {
    if (saveDataEnabled() && mode !== "intent") {
        return;
    }
    void loadReactionPickerModule();
    void queryClient.prefetchQuery({
        queryKey: queryKeys.reactionCatalog,
        queryFn: getReactionCatalog,
        staleTime: 5 * 60 * 1000,
    });
}

export function scheduleReactionPickerPreload(
    queryClient: QueryClient,
): () => void {
    if (idlePreloadScheduled || saveDataEnabled()) {
        return () => undefined;
    }
    idlePreloadScheduled = true;
    const browser = window as unknown as {
        cancelIdleCallback?: (handle: number) => void;
        requestIdleCallback?: (
            callback: () => void,
            options?: { timeout: number },
        ) => number;
    };
    const requestIdle = browser.requestIdleCallback;
    if (requestIdle) {
        const handle = requestIdle(
            () => {
                preloadReactionPickerResources(queryClient, "idle");
            },
            { timeout: 2_000 },
        );
        return () => {
            const cancelIdle = browser.cancelIdleCallback;
            if (cancelIdle) {
                cancelIdle(handle);
            }
            idlePreloadScheduled = false;
        };
    }
    const handle = window.setTimeout(() => {
        preloadReactionPickerResources(queryClient, "idle");
    }, 1_500);
    return () => {
        window.clearTimeout(handle);
        idlePreloadScheduled = false;
    };
}

export function resetReactionPickerLoaderForTests(): void {
    pickerModulePromise = null;
    idlePreloadScheduled = false;
}
