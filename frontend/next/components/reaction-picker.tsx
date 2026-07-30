"use client";

import {
    type KeyboardEvent,
    useEffect,
    useId,
    useMemo,
    useRef,
    useState,
} from "react";

import { ReactionImage } from "@/components/reaction-image";
import { loadRecentReactions } from "@/lib/reaction-storage";
import { getReactionCatalog, type ReactionDescriptor } from "@/lib/reactions";

export default function ReactionPicker({
    onClose,
    onSelect,
}: {
    onClose: () => void;
    onSelect: (reaction: ReactionDescriptor) => void;
}) {
    const [catalog, setCatalog] = useState<ReactionDescriptor[]>([]);
    const [query, setQuery] = useState("");
    const [error, setError] = useState(false);
    const [activeId, setActiveId] = useState<string | null>(null);
    const searchId = useId();
    const searchRef = useRef<HTMLInputElement>(null);
    const pickerRef = useRef<HTMLDivElement>(null);
    const recentIds = useMemo(loadRecentReactions, []);
    const catalogById = useMemo(
        () => new Map(catalog.map((item) => [item.id, item])),
        [catalog],
    );
    const recent = useMemo(
        () =>
            recentIds
                .map((reactionId) => catalogById.get(reactionId))
                .filter(
                    (item): item is ReactionDescriptor => item !== undefined,
                ),
        [catalogById, recentIds],
    );
    const visible = useMemo(() => {
        const normalized = query.trim().toLowerCase();
        if (!normalized) {
            const recentSet = new Set(recentIds);
            return catalog.filter((item) => !recentSet.has(item.id));
        }
        return catalog.filter((item) =>
            `${item.name} ${item.label}`.toLowerCase().includes(normalized),
        );
    }, [catalog, query, recentIds]);

    useEffect(() => {
        let active = true;
        searchRef.current?.focus();
        void getReactionCatalog()
            .then((loaded) => {
                if (active) {
                    setCatalog(loaded.results);
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
        if (
            !["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(
                event.key,
            )
        ) {
            return;
        }
        const buttons = Array.from(
            pickerRef.current?.querySelectorAll<HTMLButtonElement>(
                ".reaction-picker__grid button",
            ) ?? [],
        );
        const current = buttons.indexOf(
            document.activeElement as HTMLButtonElement,
        );
        if (current < 0) {
            return;
        }
        const columns =
            getComputedStyle(
                (document.activeElement as HTMLElement).closest(
                    ".reaction-picker__grid",
                ) ?? event.currentTarget,
            )
                .gridTemplateColumns.split(/\s+/)
                .filter(Boolean).length || 1;
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

    function option(item: ReactionDescriptor) {
        return (
            <button
                aria-label={`React with ${item.label}`}
                key={item.id}
                onBlur={() => {
                    setActiveId((current) =>
                        current === item.id ? null : current,
                    );
                }}
                onClick={() => {
                    onSelect(item);
                }}
                onFocus={() => {
                    setActiveId(item.id);
                }}
                onPointerEnter={(event) => {
                    if (event.pointerType === "mouse") {
                        setActiveId(item.id);
                    }
                }}
                onPointerLeave={() => {
                    setActiveId((current) =>
                        current === item.id ? null : current,
                    );
                }}
                type="button"
            >
                <ReactionImage
                    animate={activeId === item.id}
                    className="reaction-picker__image"
                    deferUntilVisible
                    reaction={item}
                />
            </button>
        );
    }

    return (
        <div
            aria-label="Choose a reaction"
            className="reaction-picker"
            onKeyDown={(event) => {
                if (event.key === "Escape") {
                    event.preventDefault();
                    onClose();
                }
            }}
            ref={pickerRef}
            role="dialog"
        >
            <div className="flex items-center gap-2">
                <label className="sr-only" htmlFor={searchId}>
                    Search reaction names
                </label>
                <input
                    className="reaction-picker__search"
                    id={searchId}
                    onChange={(event) => {
                        setQuery(event.target.value);
                    }}
                    placeholder="Search reactions"
                    ref={searchRef}
                    type="search"
                    value={query}
                />
                <button
                    aria-label="Close reaction picker"
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
                    <div
                        aria-label="Recent reactions"
                        className="reaction-picker__grid mt-1"
                        onKeyDown={gridKeyDown}
                        role="group"
                    >
                        {recent.map(option)}
                    </div>
                </div>
            ) : null}

            {error ? (
                <p className="mt-3 text-sm text-red-700" role="alert">
                    The reaction catalog could not be loaded.
                </p>
            ) : catalog.length === 0 ? (
                <p className="mt-3 text-sm text-stone-500" role="status">
                    Loading reactions…
                </p>
            ) : visible.length === 0 ? (
                <p className="mt-3 text-sm text-stone-500" role="status">
                    No reactions match your search.
                </p>
            ) : (
                <div
                    aria-label="Reaction results"
                    className="reaction-picker__grid mt-3"
                    onKeyDown={gridKeyDown}
                    role="group"
                >
                    {visible.map(option)}
                </div>
            )}
        </div>
    );
}
