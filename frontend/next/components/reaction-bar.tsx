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
import { ReactionImage } from "@/components/reaction-image";
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
    getReactionCatalog,
    getReactionParticipants,
    ReactionApiError,
    type ReactionChange,
    type ReactionDescriptor,
    type ReactionGroup,
    type ReactionParticipant,
    type ReactionTarget,
} from "@/lib/reactions";

const ReactionPicker = lazy(() => import("@/components/reaction-picker"));

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

function reactionControlLabel(label: string): string {
    const trimmed = label.trim();
    return trimmed.toLowerCase().endsWith(" reaction")
        ? trimmed
        : `${trimmed} reaction`;
}

export function ReactionBar({
    compact = false,
    initialReactions,
    onChange,
    participantsRequireActivation = false,
    slackPills = false,
    target,
}: {
    compact?: boolean;
    initialReactions: ReactionGroup[];
    onChange?: (change: ReactionChange) => void;
    participantsRequireActivation?: boolean;
    slackPills?: boolean;
    target: ReactionTarget;
}) {
    const { me, refresh, status: authStatus } = useAuth();
    const [reactions, setReactions] = useState(initialReactions);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [pendingReaction, setPendingReaction] =
        useState<ReactionDescriptor | null>(null);
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
    const restorePickerFocusRef = useRef(false);
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
                    if (change && participantGroupRef.current !== null) {
                        closeParticipants(false);
                    }
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
        [closeParticipants, instanceTargetKey, mutationTarget],
    );

    useEffect(() => {
        hydrateReactionMutation(mutationTarget, initialReactions);
    }, [initialReactions, mutationTarget, mutationTargetKey]);

    useEffect(() => {
        if (
            restorePickerFocusRef.current &&
            !pickerOpen &&
            !busy &&
            pickerTrigger.current
        ) {
            restorePickerFocusRef.current = false;
            pickerTrigger.current.focus();
        }
    }, [busy, pickerOpen]);

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
        if (authStatus !== "ready") {
            return;
        }
        const pendingId = loadPendingReaction(mutationTarget);
        if (!pendingId) {
            setPendingReaction(null);
            return;
        }
        const known = reactions
            .map((group) => group.reaction)
            .find((reaction) => reaction.id === pendingId);
        if (known) {
            setPendingReaction(known);
            return;
        }
        let active = true;
        void getReactionCatalog()
            .then((catalog) => {
                if (!active) {
                    return;
                }
                const reaction = catalog.results.find(
                    (item) => item.id === pendingId,
                );
                if (reaction) {
                    setPendingReaction(reaction);
                } else {
                    clearPendingReaction(mutationTarget);
                    setPendingReaction(null);
                }
            })
            .catch(() => {
                if (active) {
                    setError("Your saved reaction could not be restored.");
                }
            });
        return () => {
            active = false;
        };
    }, [authStatus, mutationTarget, reactions]);

    async function performToggle(
        reaction: ReactionDescriptor,
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
            savePendingReaction(target, reaction.id);
            setPendingReaction(reaction);
            setNotice(null);
            return false;
        }
        const initiatingTargetKey = instanceTargetKey;
        const mutation = coordinateReactionMutation(
            mutationTarget,
            reactions,
            reaction,
            me.csrf_token,
        );
        if (!mutation.started) {
            return false;
        }
        const outcome = await mutation.outcome;
        if (outcome.status === "authoritative") {
            rememberReaction(reaction.id);
            if (fromPending) {
                clearPendingReaction(target);
                if (
                    mountedRef.current &&
                    initiatingTargetKey === latestTargetKeyRef.current
                ) {
                    setPendingReaction(null);
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
        if (!pendingReaction) {
            return;
        }
        const alreadyPresent = reactions.some(
            (group) =>
                group.reaction.id === pendingReaction.id &&
                group.viewer_reacted,
        );
        if (alreadyPresent) {
            clearPendingReaction(target);
            setNotice(
                `Your ${pendingReaction.name} reaction is already active.`,
            );
            setPendingReaction(null);
            return;
        }
        await performToggle(pendingReaction, true);
    }

    async function openParticipants(
        group: ReactionGroup,
        cursor?: string,
        trigger?: HTMLButtonElement | null,
    ): Promise<void> {
        if (!cursor && participantGroupRef.current === group.reaction.id) {
            if (trigger) {
                participantTriggerRef.current = trigger;
            }
            return;
        }
        participantGroupRef.current = group.reaction.id;
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
                group.reaction.id,
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
                participantButtonRefs.current.get(group.reaction.id),
            );
        }
    }

    return (
        <div
            className={`reaction-bar ${compact ? "reaction-bar-compact" : ""} ${slackPills ? "reaction-bar-slack-pills" : ""}`}
        >
            <div
                aria-label="Reactions"
                className="reaction-bar__group flex flex-wrap items-center gap-2"
                role="group"
            >
                {reactions.map((group) => (
                    <span
                        className={`reaction-pill ${group.viewer_reacted ? "reaction-pill-active" : ""}`}
                        key={group.reaction.id}
                        onFocus={(event) => {
                            if (
                                !participantsRequireActivation &&
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
                            if (
                                !participantsRequireActivation &&
                                event.pointerType === "mouse"
                            ) {
                                hoverParticipants(group);
                            }
                        }}
                        onPointerUpCapture={pointerUp}
                    >
                        <button
                            aria-label={`${group.viewer_reacted ? "Remove" : "Add"} ${reactionControlLabel(group.reaction.label)}`}
                            aria-pressed={group.viewer_reacted}
                            disabled={busy || interactionDisabled}
                            onClick={() => void performToggle(group.reaction)}
                            type="button"
                        >
                            <ReactionImage
                                className="reaction-pill__asset"
                                reaction={group.reaction}
                            />
                        </button>
                        <button
                            aria-label={`View ${String(group.count)} participant${group.count === 1 ? "" : "s"} for ${group.reaction.label}`}
                            className="reaction-pill__count"
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
                                        group.reaction.id,
                                        node,
                                    );
                                } else {
                                    participantButtonRefs.current.delete(
                                        group.reaction.id,
                                    );
                                }
                            }}
                            type="button"
                        >
                            {group.count}
                        </button>
                    </span>
                ))}

                {!compact ? (
                    <button
                        aria-expanded={pickerOpen}
                        aria-haspopup="dialog"
                        aria-label="Choose reaction"
                        className="reaction-picker-trigger"
                        disabled={busy || interactionDisabled}
                        key="reaction-picker-trigger"
                        onClick={() => {
                            setPickerOpen((open) => !open);
                        }}
                        onKeyDown={(event) => {
                            if (event.key === "Escape" && pickerOpen) {
                                event.preventDefault();
                                setPickerOpen(false);
                                pickerTrigger.current?.focus();
                            }
                        }}
                        ref={pickerTrigger}
                        type="button"
                    >
                        <span
                            aria-hidden="true"
                            className="reaction-picker-trigger__icon"
                        >
                            +
                        </span>
                    </button>
                ) : null}
            </div>

            {pendingReaction ? (
                <div className="reaction-notice" role="status">
                    {canInteract ? (
                        <>
                            <span>
                                Add your saved {pendingReaction.name} reaction?
                            </span>
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
                                Sign in to add your {pendingReaction.name}{" "}
                                reaction.
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
                            setPendingReaction(null);
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
                            Loading reaction picker…
                        </p>
                    }
                >
                    <ReactionPicker
                        onClose={() => {
                            setPickerOpen(false);
                            pickerTrigger.current?.focus();
                        }}
                        onSelect={(reaction) => {
                            restorePickerFocusRef.current = true;
                            setPickerOpen(false);
                            void performToggle(reaction);
                        }}
                    />
                </Suspense>
            ) : null}

            {participantGroup ? (
                <div
                    aria-label={`${reactionControlLabel(participantGroup.reaction.label)} participants`}
                    className="reaction-participants"
                    role="dialog"
                >
                    <div className="flex items-center justify-between gap-3">
                        <strong>
                            {participantGroup.reaction.name}{" "}
                            {participantGroup.count}{" "}
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
