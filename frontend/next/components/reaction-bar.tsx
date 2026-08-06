"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
    lazy,
    type RefObject,
    Suspense,
    useCallback,
    useEffect,
    useId,
    useLayoutEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import { useAuth } from "@/components/auth-provider";
import { ReactionImage } from "@/components/reaction-image";
import { queryKeys } from "@/lib/query-keys";
import {
    loadReactionPickerModule,
    preloadReactionPickerResources,
    scheduleReactionPickerPreload,
} from "@/lib/reaction-picker-loader";
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

const ReactionPickerResults = lazy(loadReactionPickerModule);

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

function focusableElements(root: HTMLElement): HTMLElement[] {
    return Array.from(
        root.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
    ).filter((element) => !element.hasAttribute("hidden"));
}

function trapFocus(event: KeyboardEvent, root: HTMLElement): void {
    if (event.key !== "Tab") {
        return;
    }
    const focusable = focusableElements(root);
    if (focusable.length === 0) {
        event.preventDefault();
        root.focus();
        return;
    }
    const first = focusable[0];
    const last = focusable.at(-1) ?? first;
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
}

function intentionalOutsideFocus(target: EventTarget | null): boolean {
    return (
        target instanceof HTMLElement &&
        Boolean(
            target.closest(
                'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
            ),
        ) &&
        !target.closest(".reaction-bar")
    );
}

function intentionalParticipantOutsideFocus(
    target: EventTarget | null,
): boolean {
    return (
        (target instanceof HTMLElement &&
            Boolean(target.closest(".reaction-pill__count"))) ||
        intentionalOutsideFocus(target)
    );
}

function ReactionPickerShell({
    onClose,
    onSelect,
    triggerRef,
}: {
    onClose: (restoreFocus: boolean) => void;
    onSelect: (reaction: ReactionDescriptor) => void;
    triggerRef: RefObject<HTMLButtonElement | null>;
}) {
    const [query, setQuery] = useState("");
    const dialogRef = useRef<HTMLDivElement>(null);
    const searchRef = useRef<HTMLInputElement>(null);
    const searchId = useId();

    useEffect(() => {
        searchRef.current?.focus();
    }, []);

    useEffect(() => {
        const keydown = (event: KeyboardEvent): void => {
            const dialog = dialogRef.current;
            if (!dialog) {
                return;
            }
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                onClose(true);
                return;
            }
            trapFocus(event, dialog);
        };
        const pointerdown = (event: PointerEvent): void => {
            const dialog = dialogRef.current;
            const trigger = triggerRef.current;
            if (
                !dialog ||
                dialog.contains(event.target as Node) ||
                trigger?.contains(event.target as Node)
            ) {
                return;
            }
            const allowFocus = intentionalOutsideFocus(event.target);
            onClose(!allowFocus);
            if (!allowFocus) {
                event.preventDefault();
                event.stopPropagation();
            }
        };
        document.addEventListener("keydown", keydown, true);
        document.addEventListener("pointerdown", pointerdown, true);
        return () => {
            document.removeEventListener("keydown", keydown, true);
            document.removeEventListener("pointerdown", pointerdown, true);
        };
    }, [onClose, triggerRef]);

    return (
        <div
            className="reaction-picker-layer"
            onPointerDown={(event) => {
                if (event.target !== event.currentTarget) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                onClose(true);
            }}
        >
            <div
                aria-label="Choose a reaction"
                aria-modal="true"
                className="reaction-picker"
                ref={dialogRef}
                role="dialog"
                tabIndex={-1}
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
                        className="dismiss-icon"
                        onClick={() => {
                            onClose(true);
                        }}
                        type="button"
                    >
                        <span aria-hidden="true">×</span>
                    </button>
                </div>
                <Suspense
                    fallback={
                        <p
                            className="mt-3 text-sm text-stone-500"
                            role="status"
                        >
                            Loading reactions…
                        </p>
                    }
                >
                    <ReactionPickerResults onSelect={onSelect} query={query} />
                </Suspense>
            </div>
        </div>
    );
}

export function ReactionBar({
    hidePicker = false,
    initialReactions,
    onChange,
    target,
}: {
    hidePicker?: boolean;
    initialReactions: ReactionGroup[];
    onChange?: (change: ReactionChange) => void;
    target: ReactionTarget;
}) {
    const { identityKey, me, refresh, status: authStatus } = useAuth();
    const queryClient = useQueryClient();
    const [reactions, setReactions] = useState(initialReactions);
    const [pickerOpen, setPickerOpen] = useState(false);
    const [activeReactionId, setActiveReactionId] = useState<string | null>(
        null,
    );
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
    const [pickerFocusRevision, setPickerFocusRevision] = useState(0);
    const busyRef = useRef(false);
    const participantRequestRef = useRef(0);
    const participantGroupRef = useRef<string | null>(null);
    const participantTriggerRef = useRef<HTMLButtonElement | null>(null);
    const participantSurfaceRef = useRef<HTMLDivElement>(null);
    const mountedRef = useRef(true);
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

    const closePicker = useCallback((restoreFocus: boolean): void => {
        setPickerOpen(false);
        if (restoreFocus) {
            pickerTrigger.current?.focus();
        }
    }, []);

    const closeParticipants = useCallback((restoreFocus: boolean): void => {
        participantRequestRef.current += 1;
        participantGroupRef.current = null;
        const trigger = participantTriggerRef.current;
        participantTriggerRef.current = null;
        setParticipantGroup(null);
        setParticipants([]);
        setParticipantsNext(null);
        setParticipantsStatus("idle");
        if (restoreFocus && trigger) {
            trigger.focus();
        }
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            participantRequestRef.current += 1;
        };
    }, []);

    useLayoutEffect(() => {
        if (
            restorePickerFocusRef.current &&
            !busy &&
            !pickerOpen &&
            pickerTrigger.current
        ) {
            restorePickerFocusRef.current = false;
            pickerTrigger.current.focus();
        }
    }, [busy, pickerFocusRevision, pickerOpen]);

    useEffect(() => {
        closePicker(false);
        closeParticipants(false);
    }, [closeParticipants, closePicker, instanceTargetKey]);

    useEffect(() => {
        if (hidePicker) {
            return;
        }
        return scheduleReactionPickerPreload(queryClient);
    }, [hidePicker, queryClient]);

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
                        queryClient.removeQueries({
                            queryKey: [
                                "viewer",
                                identityKey,
                                "reaction-participants",
                                target.kind,
                                target.id,
                            ],
                        });
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
        [
            closeParticipants,
            identityKey,
            instanceTargetKey,
            mutationTarget,
            queryClient,
            target.id,
            target.kind,
        ],
    );

    useEffect(() => {
        hydrateReactionMutation(mutationTarget, initialReactions);
    }, [initialReactions, mutationTarget, mutationTargetKey]);

    useEffect(() => {
        if (!participantGroup) {
            return;
        }
        const frame = window.requestAnimationFrame(() => {
            const surface = participantSurfaceRef.current;
            if (surface) {
                focusableElements(surface)[0]?.focus();
            }
        });
        const keydown = (event: KeyboardEvent): void => {
            const surface = participantSurfaceRef.current;
            if (!surface) {
                return;
            }
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                closeParticipants(true);
                return;
            }
            trapFocus(event, surface);
        };
        const pointerdown = (event: PointerEvent): void => {
            const surface = participantSurfaceRef.current;
            const trigger = participantTriggerRef.current;
            if (
                !surface ||
                surface.contains(event.target as Node) ||
                trigger?.contains(event.target as Node)
            ) {
                return;
            }
            const allowFocus = intentionalParticipantOutsideFocus(event.target);
            closeParticipants(!allowFocus);
            if (!allowFocus) {
                event.preventDefault();
                event.stopPropagation();
            }
        };
        document.addEventListener("keydown", keydown, true);
        document.addEventListener("pointerdown", pointerdown, true);
        return () => {
            window.cancelAnimationFrame(frame);
            document.removeEventListener("keydown", keydown, true);
            document.removeEventListener("pointerdown", pointerdown, true);
        };
    }, [closeParticipants, participantGroup]);

    useEffect(() => {
        if (authStatus !== "ready") {
            return;
        }
        const pendingId = loadPendingReaction(
            mutationTarget,
            Date.now(),
            user?.id ?? null,
        );
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
        void queryClient
            .fetchQuery({
                queryKey: queryKeys.reactionCatalog,
                queryFn: getReactionCatalog,
                staleTime: 5 * 60 * 1000,
            })
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
                    clearPendingReaction(mutationTarget, user?.id ?? null);
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
    }, [authStatus, mutationTarget, queryClient, reactions, user?.id]);

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
                clearPendingReaction(target, user.id);
                if (
                    mountedRef.current &&
                    initiatingTargetKey === latestTargetKeyRef.current
                ) {
                    setPendingReaction(null);
                }
            }
            return true;
        }
        if (
            outcome.status === "rollback" &&
            mountedRef.current &&
            initiatingTargetKey === latestTargetKeyRef.current &&
            outcome.error instanceof ReactionApiError &&
            outcome.error.status === 403
        ) {
            savePendingReaction(target, reaction.id, Date.now(), user.id);
            setPendingReaction(reaction);
            await refresh();
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
            clearPendingReaction(target, user?.id ?? null);
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
        participantGroupRef.current = group.reaction.id;
        const requestId = participantRequestRef.current + 1;
        participantRequestRef.current = requestId;
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
            const page = await queryClient.fetchQuery({
                queryKey: queryKeys.reactionParticipants(
                    identityKey,
                    target.kind,
                    target.id,
                    group.reaction.id,
                    cursor ?? null,
                ),
                queryFn: ({ signal }) =>
                    getReactionParticipants(
                        target,
                        group.reaction.id,
                        group.participants,
                        cursor,
                        signal,
                    ),
                staleTime: 5 * 60 * 1000,
            });
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
                instanceTargetKey !== latestTargetKeyRef.current
            ) {
                return;
            }
            setParticipantsStatus("error");
        }
    }

    return (
        <div className="reaction-bar reaction-bar-compact reaction-bar-slack-pills">
            <div
                aria-label="Reactions"
                className="reaction-bar__group flex flex-wrap items-center gap-2"
                role="group"
            >
                {reactions.map((group) => (
                    <span
                        className={`reaction-pill ${group.viewer_reacted ? "reaction-pill-active" : ""}`}
                        key={group.reaction.id}
                        onBlur={(event) => {
                            if (
                                !event.currentTarget.contains(
                                    event.relatedTarget,
                                )
                            ) {
                                setActiveReactionId((current) =>
                                    current === group.reaction.id
                                        ? null
                                        : current,
                                );
                            }
                        }}
                        onFocus={() => {
                            setActiveReactionId(group.reaction.id);
                        }}
                        onPointerEnter={(event) => {
                            if (event.pointerType === "mouse") {
                                setActiveReactionId(group.reaction.id);
                            }
                        }}
                        onPointerLeave={() => {
                            setActiveReactionId((current) =>
                                current === group.reaction.id ? null : current,
                            );
                        }}
                    >
                        <button
                            aria-label={`${group.viewer_reacted ? "Remove" : "Add"} ${reactionControlLabel(group.reaction.label)}`}
                            aria-pressed={group.viewer_reacted}
                            disabled={busy || interactionDisabled}
                            onClick={() => void performToggle(group.reaction)}
                            type="button"
                        >
                            <ReactionImage
                                animate={activeReactionId === group.reaction.id}
                                className="reaction-pill__asset"
                                reaction={group.reaction}
                            />
                        </button>
                        <button
                            aria-expanded={
                                participantGroup?.reaction.id ===
                                group.reaction.id
                            }
                            aria-haspopup="dialog"
                            aria-label={`View ${String(group.count)} participant${group.count === 1 ? "" : "s"} for ${group.reaction.label}`}
                            className="reaction-pill__count"
                            disabled={busy}
                            onClick={(event) => {
                                if (
                                    participantGroupRef.current ===
                                    group.reaction.id
                                ) {
                                    closeParticipants(true);
                                    return;
                                }
                                void openParticipants(
                                    group,
                                    undefined,
                                    event.currentTarget,
                                );
                            }}
                            type="button"
                        >
                            {group.count}
                        </button>
                    </span>
                ))}

                {!hidePicker ? (
                    <button
                        aria-expanded={pickerOpen}
                        aria-haspopup="dialog"
                        aria-label="Choose reaction"
                        className="reaction-picker-trigger"
                        disabled={busy || interactionDisabled}
                        key="reaction-picker-trigger"
                        onClick={() => {
                            if (pickerOpen) {
                                closePicker(false);
                            } else {
                                preloadReactionPickerResources(
                                    queryClient,
                                    "intent",
                                );
                                setPickerOpen(true);
                            }
                        }}
                        onFocus={() => {
                            preloadReactionPickerResources(
                                queryClient,
                                "intent",
                            );
                        }}
                        onPointerDown={() => {
                            preloadReactionPickerResources(
                                queryClient,
                                "intent",
                            );
                        }}
                        onPointerEnter={(event) => {
                            if (event.pointerType === "mouse") {
                                preloadReactionPickerResources(
                                    queryClient,
                                    "hover",
                                );
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
                            <Link
                                href={`/login?next=${encodeURIComponent(target.returnTo)}`}
                                prefetch={false}
                            >
                                Login
                            </Link>
                        </>
                    )}
                    <button
                        onClick={() => {
                            clearPendingReaction(target, user?.id ?? null);
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

            {!hidePicker && pickerOpen ? (
                <ReactionPickerShell
                    onClose={closePicker}
                    onSelect={(reaction) => {
                        const selectedTargetKey = instanceTargetKey;
                        closePicker(false);
                        void performToggle(reaction).finally(() => {
                            if (
                                !mountedRef.current ||
                                selectedTargetKey !== latestTargetKeyRef.current
                            ) {
                                return;
                            }
                            restorePickerFocusRef.current = true;
                            setPickerFocusRevision((revision) => revision + 1);
                        });
                    }}
                    triggerRef={pickerTrigger}
                />
            ) : null}

            {participantGroup ? (
                <div
                    className="reaction-participant-layer"
                    onPointerDown={(event) => {
                        if (event.target !== event.currentTarget) {
                            return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        closeParticipants(true);
                    }}
                >
                    <div
                        aria-label={`${reactionControlLabel(participantGroup.reaction.label)} participants`}
                        aria-modal="true"
                        className="reaction-participants"
                        ref={participantSurfaceRef}
                        role="dialog"
                        tabIndex={-1}
                    >
                        <div className="flex items-center justify-between gap-3">
                            <strong>
                                {participantGroup.reaction.name}{" "}
                                {participantGroup.count}{" "}
                                {participantGroup.count === 1
                                    ? "person"
                                    : "people"}
                            </strong>
                            <button
                                aria-label="Close reaction participants"
                                className="dismiss-icon"
                                onClick={() => {
                                    closeParticipants(true);
                                }}
                                type="button"
                            >
                                <span aria-hidden="true">×</span>
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
                            <p
                                className="mt-2 text-sm text-red-700"
                                role="alert"
                            >
                                Participants could not be loaded.
                            </p>
                        ) : null}
                        <ul className="mt-2 space-y-1 text-sm">
                            {participants.map((participant) => (
                                <li key={participant.id}>
                                    {participant.display_name}
                                    {participant.is_site_author
                                        ? " · Author"
                                        : ""}
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
                </div>
            ) : null}
        </div>
    );
}
