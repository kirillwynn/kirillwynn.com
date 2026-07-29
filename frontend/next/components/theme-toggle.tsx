"use client";

import { useEffect, useState } from "react";

import {
    type ColorTheme,
    isColorTheme,
    resolveColorTheme,
    THEME_STORAGE_KEY,
} from "@/lib/theme";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function systemTheme(): ColorTheme {
    return typeof window.matchMedia === "function" &&
        window.matchMedia(DARK_QUERY).matches
        ? "dark"
        : "light";
}

function currentTheme(): ColorTheme {
    const value = document.documentElement.dataset.theme ?? null;
    return isColorTheme(value) ? value : systemTheme();
}

function applyTheme(theme: ColorTheme) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
}

function storedTheme(): string | null {
    try {
        return window.localStorage.getItem(THEME_STORAGE_KEY);
    } catch {
        return null;
    }
}

export function ThemeToggle() {
    const [theme, setTheme] = useState<ColorTheme | null>(null);

    useEffect(() => {
        const media =
            typeof window.matchMedia === "function"
                ? window.matchMedia(DARK_QUERY)
                : null;
        const initial = currentTheme();
        applyTheme(initial);
        setTheme(initial);

        const followSystem = (event: MediaQueryListEvent) => {
            if (!isColorTheme(storedTheme())) {
                const next = event.matches ? "dark" : "light";
                applyTheme(next);
                setTheme(next);
            }
        };
        const followStorage = (event: StorageEvent) => {
            if (event.key !== THEME_STORAGE_KEY) {
                return;
            }
            const next = resolveColorTheme(
                event.newValue,
                media?.matches ?? false,
            );
            applyTheme(next);
            setTheme(next);
        };

        media?.addEventListener("change", followSystem);
        window.addEventListener("storage", followStorage);
        return () => {
            media?.removeEventListener("change", followSystem);
            window.removeEventListener("storage", followStorage);
        };
    }, []);

    const label =
        theme === "dark"
            ? "Switch to light theme"
            : theme === "light"
              ? "Switch to dark theme"
              : "Switch color theme";

    return (
        <button
            type="button"
            className="theme-toggle"
            aria-label={label}
            title={label}
            onClick={() => {
                const next =
                    (theme ?? currentTheme()) === "dark" ? "light" : "dark";
                applyTheme(next);
                try {
                    window.localStorage.setItem(THEME_STORAGE_KEY, next);
                } catch {
                    // The in-page theme still changes when storage is blocked.
                }
                setTheme(next);
            }}
        >
            <svg
                className="theme-icon theme-icon-moon"
                aria-hidden="true"
                viewBox="0 0 24 24"
                width="18"
                height="18"
            >
                <path
                    d="M20.3 15.1A8.5 8.5 0 0 1 8.9 3.7 8.5 8.5 0 1 0 20.3 15.1Z"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                />
            </svg>
            <svg
                className="theme-icon theme-icon-sun"
                aria-hidden="true"
                viewBox="0 0 24 24"
                width="18"
                height="18"
            >
                <circle
                    cx="12"
                    cy="12"
                    r="3.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                />
                <path
                    d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"
                    fill="none"
                    stroke="currentColor"
                    strokeLinecap="round"
                    strokeWidth="1.8"
                />
            </svg>
        </button>
    );
}
