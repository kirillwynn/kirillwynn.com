"use client";

import {
    type KeyboardEvent,
    useId,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { loadRecentReactions } from "@/lib/reaction-storage";

type EmojiOption = {
    category: string;
    emoji: string;
    name: string;
    keywords: string[];
};

type EmojiDataset = {
    categories: Array<{ id: string; emojis: string[] }>;
    emojis: Record<
        string,
        {
            name: string;
            keywords: string[];
            skins: Array<{ native: string }>;
        }
    >;
};

async function options(): Promise<EmojiOption[]> {
    const module = await import("@emoji-mart/data");
    const data = module.default as EmojiDataset;
    const values: EmojiOption[] = [];
    const seen = new Set<string>();
    for (const category of data.categories) {
        for (const id of category.emojis) {
            const item = data.emojis[id];
            for (const skin of item.skins) {
                if (seen.has(skin.native)) {
                    continue;
                }
                seen.add(skin.native);
                values.push({
                    category: category.id,
                    emoji: skin.native,
                    name: item.name,
                    keywords: item.keywords,
                });
            }
        }
    }
    return values;
}

export default function EmojiPicker({
    onClose,
    onSelect,
}: {
    onClose: () => void;
    onSelect: (emoji: string) => void;
}) {
    const [all, setAll] = useState<EmojiOption[]>([]);
    const [query, setQuery] = useState("");
    const [category, setCategory] = useState("people");
    const [error, setError] = useState(false);
    const searchId = useId();
    const searchRef = useRef<HTMLInputElement>(null);
    const gridRef = useRef<HTMLDivElement>(null);
    const recent = useMemo(loadRecentReactions, []);
    const categories = useMemo(
        () => Array.from(new Set(all.map((item) => item.category))),
        [all],
    );
    const visible = useMemo(() => {
        const normalized = query.trim().toLocaleLowerCase();
        if (normalized) {
            return all.filter((item) =>
                [item.name, ...item.keywords]
                    .join(" ")
                    .toLocaleLowerCase()
                    .includes(normalized),
            );
        }
        return all.filter((item) => item.category === category);
    }, [all, category, query]);

    useEffect(() => {
        let active = true;
        void options()
            .then((loaded) => {
                if (active) {
                    setAll(loaded);
                    setCategory((current) =>
                        loaded.some((item) => item.category === current)
                            ? current
                            : (loaded[0]?.category ?? ""),
                    );
                    searchRef.current?.focus();
                }
            })
            .catch(() => {
                if (active) {
                    setError(true);
                }
            });
        return () => {
            active = false;
        };
    }, []);

    function gridKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
        if (event.key === "Escape") {
            event.preventDefault();
            onClose();
            return;
        }
        if (
            !["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(
                event.key,
            )
        ) {
            return;
        }
        const buttons = Array.from(
            gridRef.current?.querySelectorAll<HTMLButtonElement>("button") ??
                [],
        );
        const current = buttons.indexOf(
            document.activeElement as HTMLButtonElement,
        );
        if (current < 0) {
            return;
        }
        const columns = 8;
        const delta =
            event.key === "ArrowRight"
                ? 1
                : event.key === "ArrowLeft"
                  ? -1
                  : event.key === "ArrowDown"
                    ? columns
                    : -columns;
        event.preventDefault();
        buttons[(current + delta + buttons.length) % buttons.length]?.focus();
    }

    return (
        <div
            aria-label="Choose an emoji"
            className="emoji-picker"
            onKeyDown={(event) => {
                if (event.key === "Escape") {
                    event.preventDefault();
                    onClose();
                }
            }}
            role="dialog"
        >
            <div className="flex items-center gap-2">
                <label className="sr-only" htmlFor={searchId}>
                    Search emoji names and keywords
                </label>
                <input
                    className="emoji-search"
                    id={searchId}
                    onChange={(event) => {
                        setQuery(event.target.value);
                    }}
                    placeholder="Search emoji"
                    ref={searchRef}
                    type="search"
                    value={query}
                />
                <button
                    aria-label="Close emoji picker"
                    className="comment-action"
                    onClick={onClose}
                    type="button"
                >
                    Close
                </button>
            </div>

            {!query && recent.length ? (
                <div className="mt-3">
                    <p className="text-xs font-semibold text-stone-600">
                        Recent
                    </p>
                    <div className="emoji-grid mt-1">
                        {recent.map((emoji) => (
                            <button
                                aria-label={`React with ${emoji}`}
                                key={emoji}
                                onClick={() => {
                                    onSelect(emoji);
                                }}
                                type="button"
                            >
                                {emoji}
                            </button>
                        ))}
                    </div>
                </div>
            ) : null}

            {!query ? (
                <div
                    aria-label="Emoji categories"
                    className="emoji-categories"
                    role="tablist"
                >
                    {categories.map((value) => (
                        <button
                            aria-selected={category === value}
                            key={value}
                            onClick={() => {
                                setCategory(value);
                            }}
                            role="tab"
                            type="button"
                        >
                            {value}
                        </button>
                    ))}
                </div>
            ) : null}

            {error ? (
                <p className="mt-3 text-sm text-red-700" role="alert">
                    The emoji picker could not be loaded.
                </p>
            ) : all.length === 0 ? (
                <p className="mt-3 text-sm text-stone-500" role="status">
                    Loading emoji…
                </p>
            ) : (
                <div
                    aria-label="Emoji results"
                    className="emoji-grid mt-3"
                    onKeyDown={gridKeyDown}
                    ref={gridRef}
                    role="grid"
                >
                    {visible.map((item) => (
                        <button
                            aria-label={item.name}
                            key={item.emoji}
                            onClick={() => {
                                onSelect(item.emoji);
                            }}
                            role="gridcell"
                            type="button"
                        >
                            {item.emoji}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
