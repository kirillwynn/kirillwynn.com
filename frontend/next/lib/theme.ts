export const THEME_STORAGE_KEY = "kirillwynn-theme";

export type ColorTheme = "light" | "dark";

export function isColorTheme(value: string | null): value is ColorTheme {
    return value === "light" || value === "dark";
}

export function resolveColorTheme(
    storedTheme: string | null,
    prefersDark: boolean,
): ColorTheme {
    return isColorTheme(storedTheme)
        ? storedTheme
        : prefersDark
          ? "dark"
          : "light";
}

export const THEME_INIT_SCRIPT = `
(() => {
    const storageKey = ${JSON.stringify(THEME_STORAGE_KEY)};
    let storedTheme = null;
    try {
        storedTheme = window.localStorage.getItem(storageKey);
    } catch {}
    const theme =
        storedTheme === "light" || storedTheme === "dark"
            ? storedTheme
            : typeof window.matchMedia === "function" &&
                window.matchMedia("(prefers-color-scheme: dark)").matches
              ? "dark"
              : "light";
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
})();
`;
