const feedScrollPositions = new Map<string, number>();
const FEED_SCROLL_STORAGE_PREFIX = "kirillwynn:feed-scroll:";
const RESTORATION_DEADLINE_MS = 2_000;
let restorationGeneration = 0;

function storageKey(query: string): string {
    return `${FEED_SCROLL_STORAGE_PREFIX}${encodeURIComponent(query)}`;
}

export function readFeedScroll(query: string): number | undefined {
    const memory = feedScrollPositions.get(query);
    if (memory !== undefined) {
        return memory;
    }
    try {
        const stored = window.sessionStorage.getItem(storageKey(query));
        if (stored && /^\d+$/.test(stored)) {
            return Number(stored);
        }
    } catch {
        // Scroll restoration remains an in-memory best effort.
    }
    return undefined;
}

export function saveFeedScroll(query: string, scrollY: number): void {
    const bounded = Math.max(0, Math.round(scrollY));
    feedScrollPositions.set(query, bounded);
    try {
        window.sessionStorage.setItem(storageKey(query), String(bounded));
    } catch {
        // Scroll restoration remains an in-memory best effort.
    }
}

export function scheduleFeedScrollRestoration(query: string): void {
    const saved = readFeedScroll(query);
    if (saved === undefined) {
        return;
    }
    const generation = ++restorationGeneration;
    const deadline = window.performance.now() + RESTORATION_DEADLINE_MS;
    const restore = () => {
        if (generation !== restorationGeneration) {
            return;
        }
        const currentQuery = new URLSearchParams(window.location.search)
            .get("q")
            ?.trim();
        if (
            window.location.pathname === "/" &&
            (currentQuery ?? "") === query
        ) {
            window.scrollTo({ top: saved });
            if (Math.abs(window.scrollY - saved) <= 2) {
                return;
            }
        }
        if (window.performance.now() < deadline) {
            window.requestAnimationFrame(restore);
        }
    };
    window.requestAnimationFrame(restore);
}
