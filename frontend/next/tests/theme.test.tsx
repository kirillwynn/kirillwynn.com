// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/theme-toggle";
import {
    resolveColorTheme,
    THEME_INIT_SCRIPT,
    THEME_STORAGE_KEY,
} from "@/lib/theme";

let mediaMatches = false;
let mediaListeners = new Set<EventListener>();
let root: Root | null = null;

function mediaQueryList(): MediaQueryList {
    return {
        get matches() {
            return mediaMatches;
        },
        media: "(prefers-color-scheme: dark)",
        onchange: null,
        addEventListener: ((
            _type: string,
            listener: EventListenerOrEventListenerObject,
        ) => {
            if (typeof listener === "function") {
                mediaListeners.add(listener);
            }
        }) as MediaQueryList["addEventListener"],
        removeEventListener: ((
            _type: string,
            listener: EventListenerOrEventListenerObject,
        ) => {
            if (typeof listener === "function") {
                mediaListeners.delete(listener);
            }
        }) as MediaQueryList["removeEventListener"],
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
    };
}

async function renderToggle() {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
        root?.render(<ThemeToggle />);
        await Promise.resolve();
    });
    return container.querySelector("button");
}

async function changeSystemTheme(prefersDark: boolean) {
    mediaMatches = prefersDark;
    const event = { matches: prefersDark } as MediaQueryListEvent;
    await act(async () => {
        for (const listener of mediaListeners) {
            listener(event);
        }
        await Promise.resolve();
    });
}

beforeEach(() => {
    mediaMatches = false;
    mediaListeners = new Set();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.removeProperty("color-scheme");
    vi.stubGlobal(
        "matchMedia",
        vi.fn(() => mediaQueryList()),
    );
    (
        globalThis as typeof globalThis & {
            IS_REACT_ACT_ENVIRONMENT: boolean;
        }
    ).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
    if (root) {
        act(() => {
            root?.unmount();
        });
        root = null;
    }
    vi.unstubAllGlobals();
    document.body.replaceChildren();
});

describe("color theme", () => {
    it("resolves a saved choice before the system preference", () => {
        expect(resolveColorTheme(null, false)).toBe("light");
        expect(resolveColorTheme(null, true)).toBe("dark");
        expect(resolveColorTheme("light", true)).toBe("light");
        expect(resolveColorTheme("dark", false)).toBe("dark");
        expect(resolveColorTheme("invalid", true)).toBe("dark");
        expect(THEME_INIT_SCRIPT).toContain(THEME_STORAGE_KEY);
        expect(THEME_INIT_SCRIPT).toContain("prefers-color-scheme: dark");
    });

    it("announces, applies, and persists the opposite theme", async () => {
        document.documentElement.dataset.theme = "dark";
        const button = await renderToggle();

        expect(button?.getAttribute("aria-label")).toBe(
            "Switch to light theme",
        );
        await act(async () => {
            button?.click();
            await Promise.resolve();
        });

        expect(document.documentElement.dataset.theme).toBe("light");
        expect(document.documentElement.style.colorScheme).toBe("light");
        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
        expect(button?.getAttribute("aria-label")).toBe("Switch to dark theme");
    });

    it("follows system changes only until a manual choice exists", async () => {
        document.documentElement.dataset.theme = "light";
        const button = await renderToggle();

        await changeSystemTheme(true);
        expect(document.documentElement.dataset.theme).toBe("dark");

        await act(async () => {
            button?.click();
            await Promise.resolve();
        });
        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");

        await changeSystemTheme(true);
        expect(document.documentElement.dataset.theme).toBe("light");
    });
});
