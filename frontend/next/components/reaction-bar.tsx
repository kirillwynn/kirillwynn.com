"use client";

import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
    clearPendingReaction,
    loadPendingReaction,
    rememberReaction,
    savePendingReaction,
} from "@/lib/reaction-storage";
import {
    getReactionConfig,
    getReactionParticipants,
    ReactionApiError,
    reactionParticipantPath,
    toggleReaction,
    type ReactionGroup,
    type ReactionParticipant,
    type ReactionTarget,
} from "@/lib/reactions";

const EmojiPicker = lazy(() => import("@/components/emoji-picker"));

function optimisticGroups(
    current: ReactionGroup[],
    target: ReactionTarget,
    emoji: string,
): ReactionGroup[] {
    const existing = current.find((group) => group.emoji === emoji);
    if (!existing) {
        return [
            ...current,
            {
                emoji,
                count: 1,
                viewer_reacted: true,
                participants: reactionParticipantPath(target, emoji),
            },
        ].sort((left, right) =>
            left.emoji < right.emoji ? -1 : left.emoji > right.emoji ? 1 : 0,
        );
    }
    const count = existing.count + (existing.viewer_reacted ? -1 : 1);
    if (count === 0) {
        return current.filter((group) => group.emoji !== emoji);
    }
    return current.map((group) =>
        group.emoji === emoji
            ? {
                  ...group,
                  count,
                  viewer_reacted: !group.viewer_reacted,
              }
            : group,
    );
}

function reactionError(error: unknown): string {
    if (error instanceof ReactionApiError) {
        if (error.status === 429 && error.retryAfter) {
            return `${error.message} Retry in about ${String(error.retryAfter)} seconds.`;
        }
        if (error.status === 403) {
            return "Your session expired or this account is read-only. Sign in again to react.";
        }
        return error.message;
    }
    return "The reaction could not be saved. Your previous state was restored.";
}

export function ReactionBar({
    initialReactions,
    onChange,
    target,
}: {
    initialReactions: ReactionGroup[];
    onChange?: (reactions: ReactionGroup[]) => void;
    target: ReactionTarget;
}) {
    const { me, refresh, status: authStatus } = useAuth();
    const [reactions, setReactions] = useState(initialReactions);
    const [quick, setQuick] = useState<string[]>([]);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [pendingEmoji, setPendingEmoji] = useState<string | null>(null);
    const [participantGroup, setParticipantGroup] =
        useState<ReactionGroup | null>(null);
    const [participants, setParticipants] = useState<ReactionParticipant[]>([]);
    const [participantsNext, setParticipantsNext] = useState<string | null>(
        null,
    );
    const [participantsStatus, setParticipantsStatus] = useState<
        "idle" | "loading" | "ready" | "error"
    >("idle");
    const pickerTrigger = useRef<HTMLButtonElement>(null);
    const busyRef = useRef(false);
    const user = me?.authenticated ? me.user : null;
    const canInteract = Boolean(user?.can_interact);
    const interactionDisabled = Boolean(user && !canInteract);

    useEffect(() => {
        setReactions(initialReactions);
    }, [initialReactions]);

    useEffect(() => {
        let active = true;
        void getReactionConfig()
            .then((config) => {
                if (active) {
                    setQuick(config.quick_reactions);
                }
            })
            .catch(() => {
                if (active) {
                    setError("Quick reactions could not be loaded.");
                }
            });
        return () => {
            active = false;
        };
    }, []);

    useEffect(() => {
        if (authStatus !== "ready") {
            return;
        }
        setPendingEmoji(loadPendingReaction(target));
    }, [authStatus, target]);

    function update(next: ReactionGroup[]): void {
        setReactions(next);
        onChange?.(next);
    }

    async function performToggle(
        emoji: string,
        fromPending = false,
    ): Promise<boolean> {
        if (busyRef.current) {
            return false;
        }
        if (interactionDisabled) {
            setError(
                "This account is read-only. You can still view reaction participants.",
            );
            return false;
        }
        if (!user || !me?.csrf_token) {
            savePendingReaction(target, emoji);
            setPendingEmoji(emoji);
            setNotice(null);
            return false;
        }
        const previous = reactions;
        busyRef.current = true;
        setBusy(true);
        setError(null);
        setNotice(null);
        update(optimisticGroups(previous, target, emoji));
        try {
            const authoritative = await toggleReaction(
                target,
                emoji,
                me.csrf_token,
            );
            update(authoritative);
            rememberReaction(emoji);
            if (fromPending) {
                clearPendingReaction(target, emoji);
                setPendingEmoji(null);
            }
            return true;
        } catch (caught) {
            update(previous);
            setError(reactionError(caught));
            if (caught instanceof ReactionApiError && caught.status === 403) {
                await refresh();
            }
            return false;
        } finally {
            busyRef.current = false;
            setBusy(false);
        }
    }

    async function confirmPending(): Promise<void> {
        if (!pendingEmoji) {
            return;
        }
        const alreadyPresent = reactions.some(
            (group) => group.emoji === pendingEmoji && group.viewer_reacted,
        );
        if (alreadyPresent) {
            clearPendingReaction(target, pendingEmoji);
            setNotice(`Your ${pendingEmoji} reaction is already active.`);
            setPendingEmoji(null);
            return;
        }
        await performToggle(pendingEmoji, true);
    }

    async function openParticipants(
        group: ReactionGroup,
        cursor?: string,
    ): Promise<void> {
        if (!cursor && participantGroup?.emoji === group.emoji) {
            return;
        }
        setParticipantGroup(group);
        setParticipantsStatus("loading");
        if (!cursor) {
            setParticipants([]);
        }
        try {
            const page = await getReactionParticipants(
                target,
                group.emoji,
                group.participants,
                cursor,
            );
            setParticipants((current) =>
                cursor ? [...current, ...page.results] : page.results,
            );
            setParticipantsNext(page.next);
            setParticipantsStatus("ready");
        } catch {
            setParticipantsStatus("error");
        }
    }

    const quickOnly = quick.filter(
        (emoji) => !reactions.some((group) => group.emoji === emoji),
    );

    return (
        <div className="reaction-bar">
            <div
                aria-label="Reactions"
                className="flex flex-wrap items-center gap-2"
                role="group"
            >
                {reactions.map((group) => (
                    <span
                        className={`reaction-pill ${group.viewer_reacted ? "reaction-pill-active" : ""}`}
                        key={group.emoji}
                        onFocus={() => void openParticipants(group)}
                        onMouseEnter={() => void openParticipants(group)}
                    >
                        <button
                            aria-label={`${group.viewer_reacted ? "Remove" : "Add"} ${group.emoji} reaction`}
                            aria-pressed={group.viewer_reacted}
                            disabled={busy || interactionDisabled}
                            onClick={() => void performToggle(group.emoji)}
                            type="button"
                        >
                            <span aria-hidden="true">{group.emoji}</span>
                        </button>
                        <button
                            aria-label={`View ${String(group.count)} participant${group.count === 1 ? "" : "s"} for ${group.emoji}`}
                            disabled={busy}
                            onClick={() => void openParticipants(group)}
                            type="button"
                        >
                            {group.count}
                        </button>
                    </span>
                ))}

                {quickOnly.map((emoji) => (
                    <button
                        aria-label={`React with ${emoji}`}
                        className="quick-reaction"
                        disabled={busy || interactionDisabled}
                        key={emoji}
                        onClick={() => void performToggle(emoji)}
                        type="button"
                    >
                        {emoji}
                    </button>
                ))}

                <button
                    aria-expanded={pickerOpen}
                    aria-label="Open full emoji picker"
                    className="quick-reaction"
                    disabled={busy || interactionDisabled}
                    onClick={() => {
                        setPickerOpen((open) => !open);
                    }}
                    ref={pickerTrigger}
                    type="button"
                >
                    +
                </button>
            </div>

            {pendingEmoji ? (
                <div className="reaction-notice" role="status">
                    {canInteract ? (
                        <>
                            <span>Add your saved {pendingEmoji} reaction?</span>
                            <button
                                disabled={busy}
                                onClick={() => void confirmPending()}
                                type="button"
                            >
                                Confirm
                            </button>
                        </>
                    ) : user ? (
                        <span>
                            This account is read-only, so the saved reaction
                            cannot be added.
                        </span>
                    ) : (
                        <>
                            <span>
                                Sign in to add your {pendingEmoji} reaction.
                            </span>
                            <a
                                href={`/login?next=${encodeURIComponent(target.returnTo)}`}
                            >
                                Login
                            </a>
                        </>
                    )}
                    <button
                        onClick={() => {
                            clearPendingReaction(target, pendingEmoji);
                            setPendingEmoji(null);
                        }}
                        type="button"
                    >
                        Discard
                    </button>
                </div>
            ) : null}

            {notice ? (
                <p className="mt-2 text-sm text-stone-600" role="status">
                    {notice}
                </p>
            ) : null}
            {error ? (
                <p className="mt-2 text-sm text-red-700" role="alert">
                    {error}
                </p>
            ) : null}

            {pickerOpen ? (
                <Suspense
                    fallback={
                        <p
                            className="mt-3 text-sm text-stone-500"
                            role="status"
                        >
                            Loading emoji picker…
                        </p>
                    }
                >
                    <EmojiPicker
                        onClose={() => {
                            setPickerOpen(false);
                            pickerTrigger.current?.focus();
                        }}
                        onSelect={(emoji) => {
                            setPickerOpen(false);
                            void performToggle(emoji);
                            pickerTrigger.current?.focus();
                        }}
                    />
                </Suspense>
            ) : null}

            {participantGroup ? (
                <div
                    aria-label={`${participantGroup.emoji} reaction participants`}
                    className="reaction-participants"
                    role="dialog"
                >
                    <div className="flex items-center justify-between gap-3">
                        <strong>
                            {participantGroup.emoji} {participantGroup.count}{" "}
                            {participantGroup.count === 1 ? "person" : "people"}
                        </strong>
                        <button
                            aria-label="Close reaction participants"
                            className="comment-action"
                            onClick={() => {
                                setParticipantGroup(null);
                            }}
                            type="button"
                        >
                            Close
                        </button>
                    </div>
                    {participantsStatus === "loading" &&
                    participants.length === 0 ? (
                        <p
                            className="mt-2 text-sm text-stone-500"
                            role="status"
                        >
                            Loading participants…
                        </p>
                    ) : null}
                    {participantsStatus === "error" ? (
                        <p className="mt-2 text-sm text-red-700" role="alert">
                            Participants could not be loaded.
                        </p>
                    ) : null}
                    <ul className="mt-2 space-y-1 text-sm">
                        {participants.map((participant) => (
                            <li key={participant.id}>
                                {participant.display_name}
                                {participant.is_site_author ? " · Author" : ""}
                            </li>
                        ))}
                    </ul>
                    {participantsNext ? (
                        <button
                            className="comment-action mt-2"
                            disabled={participantsStatus === "loading"}
                            onClick={() =>
                                void openParticipants(
                                    participantGroup,
                                    participantsNext,
                                )
                            }
                            type="button"
                        >
                            Load more
                        </button>
                    ) : null}
                </div>
            ) : null}
        </div>
    );
}
