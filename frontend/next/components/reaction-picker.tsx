"use client";

import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, useMemo, useRef, useState } from "react";

import { ReactionImage } from "@/components/reaction-image";
import { queryKeys } from "@/lib/query-keys";
import { loadRecentReactions } from "@/lib/reaction-storage";
import { getReactionCatalog, type ReactionDescriptor } from "@/lib/reactions";

export default function ReactionPickerResults({
    onSelect,
    query,
}: {
    onSelect: (reaction: ReactionDescriptor) => void;
    query: string;
}) {
    const catalogQuery = useQuery({
        queryKey: queryKeys.reactionCatalog,
        queryFn: getReactionCatalog,
        staleTime: 5 * 60 * 1000,
    });
    const catalog = catalogQuery.data?.results ?? [];
    const [activeId, setActiveId] = useState<string | null>(null);
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
        if (current < 0 || buttons.length === 0) {
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
        <div ref={pickerRef}>
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

            {catalogQuery.isError ? (
                <p className="mt-3 text-sm text-red-700" role="alert">
                    The reaction catalog could not be loaded.
                </p>
            ) : catalogQuery.isPending ? (
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
