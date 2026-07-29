"use client";

import {
    lazy,
    Suspense,
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { useAuth } from "@/components/auth-provider";
import {
    clearPendingReaction,
    loadPendingReaction,
    rememberReaction,
    savePendingReaction,
} from "@/lib/reaction-storage";
import {
    coordinateReactionMutation,
    hydrateReactionMutation,
    reactionMutationTargetKey,
    subscribeReactionMutation,
} from "@/lib/reaction-mutation-coordinator";
import {
    getReactionConfig,
    getReactionParticipants,
    ReactionApiError,
    type ReactionChange,
    type ReactionGroup,
    type ReactionParticipant,
    type ReactionTarget,
} from "@/lib/reactions";

const EmojiPicker = lazy(() => import("@/components/emoji-picker"));

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
    compact = false,
    initialReactions,
    onChange,
    target,
}: {
    compact?: boolean;
    initialReactions: ReactionGroup[];
    onChange?: (change: ReactionChange) => void;
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
    const participantRequestRef = useRef(0);
    const participantAbortRef = useRef<AbortController | null>(null);
    const participantGroupRef = useRef<string | null>(null);
    const participantTriggerRef = useRef<HTMLButtonElement | null>(null);
    const suppressParticipantFocusRef = useRef(false);
    const participantButtonRefs = useRef(new Map<string, HTMLButtonElement>());
    const mountedRef = useRef(true);
    const pointerTypeRef = useRef<string | null>(null);
    const lastTouchAtRef = useRef(0);
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;
    const initialReactionsRef = useRef(initialReactions);
    initialReactionsRef.current = initialReactions;
    const mutationTarget = useMemo(
        () => target,
        [target.id, target.kind, target.returnTo, target.slug],
    );
    const mutationTargetKey = reactionMutationTargetKey(mutationTarget);
    const instanceTargetKey = `${target.kind}:${String(target.id)}:${target.slug}`;
    const latestTargetKeyRef = useRef(instanceTargetKey);
    latestTargetKeyRef.current = instanceTargetKey;
    const user = me?.authenticated ? me.user : null;
    const canInteract = Boolean(user?.can_interact);
    const interactionDisabled = Boolean(user && !canInteract);

    const closeParticipants = useCallback((restoreFocus: boolean): void => {
        participantRequestRef.current += 1;
        participantAbortRef.current?.abort();
        participantAbortRef.current = null;
        participantGroupRef.current = null;
        const trigger = participantTriggerRef.current;
        participantTriggerRef.current = null;
        setParticipantGroup(null);
        setParticipants([]);
        setParticipantsNext(null);
        setParticipantsStatus("idle");
        if (restoreFocus && trigger) {
            suppressParticipantFocusRef.current = true;
            trigger.focus();
            suppressParticipantFocusRef.current = false;
        }
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            participantRequestRef.current += 1;
            participantAbortRef.current?.abort();
        };
    }, []);

    useEffect(() => {
        closeParticipants(false);
    }, [closeParticipants, instanceTargetKey]);

    useEffect(
        () =>
            subscribeReactionMutation(
                mutationTarget,
                initialReactionsRef.current,
                ({ change, error: mutationError, snapshot }) => {
                    if (
                        !mountedRef.current ||
                        instanceTargetKey !== latestTargetKeyRef.current
                    ) {
                        return;
                    }
                    busyRef.current = snapshot.busy;
                    setBusy(snapshot.busy);
                    setReactions(snapshot.reactions);
                    if (change) {
                        if (change.source === "optimistic") {
                            setError(null);
                            setNotice(null);
                        } else if (change.source === "authoritative") {
                            setError(null);
                        }
                        onChangeRef.current?.(change);
                    }
                    if (mutationError !== undefined) {
                        setError(reactionError(mutationError));
                    }
                },
            ),
        [instanceTargetKey, mutationTarget],
    );

    useEffect(() => {
        hydrateReactionMutation(mutationTarget, initialReactions);
    }, [initialReactions, mutationTarget, mutationTargetKey]);

    useEffect(() => {
        function keydown(event: KeyboardEvent): void {
            if (
                event.key === "Escape" &&
                participantGroupRef.current !== null
            ) {
                event.preventDefault();
                closeParticipants(true);
            }
        }
        document.addEventListener("keydown", keydown);
        return () => {
            document.removeEventListener("keydown", keydown);
        };
    }, [closeParticipants]);

    useEffect(() => {
        if (compact) {
            setQuick([]);
            return;
        }
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
    }, [compact]);

    useEffect(() => {
        if (authStatus !== "ready") {
            return;
        }
        setPendingEmoji(loadPendingReaction(target));
    }, [authStatus, target.id, target.kind, target.slug]);

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
        const initiatingTargetKey = instanceTargetKey;
        const mutation = coordinateReactionMutation(
            mutationTarget,
            reactions,
            emoji,
            me.csrf_token,
        );
        if (!mutation.started) {
            return false;
        }
        const outcome = await mutation.outcome;
        if (outcome.status === "authoritative") {
            rememberReaction(emoji);
            if (fromPending) {
                clearPendingReaction(target);
                if (
                    mountedRef.current &&
                    initiatingTargetKey === latestTargetKeyRef.current
                ) {
                    setPendingEmoji(null);
                }
            }
            return true;
        }
        if (outcome.status === "rollback") {
            if (
                mountedRef.current &&
                initiatingTargetKey === latestTargetKeyRef.current &&
                outcome.error instanceof ReactionApiError &&
                outcome.error.status === 403
            ) {
                await refresh();
            }
        }
        return false;
    }

    async function confirmPending(): Promise<void> {
        if (!pendingEmoji) {
            return;
        }
        const alreadyPresent = reactions.some(
            (group) => group.emoji === pendingEmoji && group.viewer_reacted,
        );
        if (alreadyPresent) {
            clearPendingReaction(target);
            setNotice(`Your ${pendingEmoji} reaction is already active.`);
            setPendingEmoji(null);
            return;
        }
        await performToggle(pendingEmoji, true);
    }

    async function openParticipants(
        group: ReactionGroup,
        cursor?: string,
        trigger?: HTMLButtonElement | null,
    ): Promise<void> {
        if (!cursor && participantGroupRef.current === group.emoji) {
            if (trigger) {
                participantTriggerRef.current = trigger;
            }
            return;
        }
        participantGroupRef.current = group.emoji;
        const requestId = participantRequestRef.current + 1;
        participantRequestRef.current = requestId;
        participantAbortRef.current?.abort();
        const controller = new AbortController();
        participantAbortRef.current = controller;
        if (trigger) {
            participantTriggerRef.current = trigger;
        }
        setParticipantGroup(group);
        setParticipantsStatus("loading");
        if (!cursor) {
            setParticipants([]);
            setParticipantsNext(null);
        }
        try {
            const page = await getReactionParticipants(
                target,
                group.emoji,
                group.participants,
                cursor,
                controller.signal,
            );
            if (
                !mountedRef.current ||
                requestId !== participantRequestRef.current ||
                instanceTargetKey !== latestTargetKeyRef.current
            ) {
                return;
            }
            setParticipants((current) =>
                Array.from(
                    new Map(
                        (cursor
                            ? [...current, ...page.results]
                            : page.results
                        ).map((participant) => [participant.id, participant]),
                    ).values(),
                ),
            );
            setParticipantsNext(page.next);
            setParticipantsStatus("ready");
        } catch {
            if (
                !mountedRef.current ||
                requestId !== participantRequestRef.current ||
                controller.signal.aborted ||
                instanceTargetKey !== latestTargetKeyRef.current
            ) {
                return;
            }
            setParticipantsStatus("error");
        } finally {
            if (requestId === participantRequestRef.current) {
                participantAbortRef.current = null;
            }
        }
    }

    function pointerDown(pointerType: string): void {
        pointerTypeRef.current = pointerType;
        if (pointerType === "touch") {
            lastTouchAtRef.current = Date.now();
        }
    }

    function pointerUp(): void {
        window.setTimeout(() => {
            pointerTypeRef.current = null;
        }, 0);
    }

    function hoverParticipants(group: ReactionGroup): void {
        if (
            window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
            Date.now() - lastTouchAtRef.current > 1000
        ) {
            void openParticipants(
                group,
                undefined,
                participantButtonRefs.current.get(group.emoji),
            );
        }
    }

    const quickOnly = compact
        ? []
        : quick.filter(
              (emoji) => !reactions.some((group) => group.emoji === emoji),
          );

    return (
        <div
            className={`reaction-bar ${compact ? "reaction-bar-compact" : ""}`}
        >
            <div
                aria-label="Reactions"
                className="flex flex-wrap items-center gap-2"
                role="group"
            >
                {reactions.map((group) => (
                    <span
                        className={`reaction-pill ${group.viewer_reacted ? "reaction-pill-active" : ""}`}
                        key={group.emoji}
                        onFocus={(event) => {
                            if (
                                pointerTypeRef.current !== "touch" &&
                                !suppressParticipantFocusRef.current
                            ) {
                                void openParticipants(
                                    group,
                                    undefined,
                                    event.target instanceof HTMLButtonElement
                                        ? event.target
                                        : undefined,
                                );
                            }
                        }}
                        onPointerCancel={pointerUp}
                        onPointerDownCapture={(event) => {
                            pointerDown(event.pointerType);
                        }}
                        onPointerEnter={(event) => {
                            if (event.pointerType === "mouse") {
                                hoverParticipants(group);
                            }
                        }}
                        onPointerUpCapture={pointerUp}
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
                            onClick={(event) =>
                                void openParticipants(
                                    group,
                                    undefined,
                                    event.currentTarget,
                                )
                            }
                            ref={(node) => {
                                if (node) {
                                    participantButtonRefs.current.set(
                                        group.emoji,
                                        node,
                                    );
                                } else {
                                    participantButtonRefs.current.delete(
                                        group.emoji,
                                    );
                                }
                            }}
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

                {!compact ? (
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
                ) : null}
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
                            clearPendingReaction(target);
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

            {!compact && pickerOpen ? (
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
                                closeParticipants(true);
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
                                    participantTriggerRef.current,
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
