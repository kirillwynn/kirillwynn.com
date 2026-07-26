import {
    reactionParticipantPath,
    toggleReaction,
    type ReactionChange,
    type ReactionGroup,
    type ReactionTarget,
} from "@/lib/reactions";

export type ReactionMutationSnapshot = {
    busy: boolean;
    reactions: ReactionGroup[];
};

export type ReactionMutationEvent = {
    change?: ReactionChange;
    error?: unknown;
    snapshot: ReactionMutationSnapshot;
};

export type ReactionMutationOutcome =
    | {
          reactions: ReactionGroup[];
          revision: number;
          status: "authoritative";
      }
    | {
          error: unknown;
          reactions: ReactionGroup[];
          revision: number;
          status: "rollback";
      }
    | {
          status: "stale";
      };

type Listener = (event: ReactionMutationEvent) => void;

type ActiveMutation = {
    revision: number;
};

type TargetEntry = {
    active: ActiveMutation | null;
    listeners: Set<Listener>;
    reactions: ReactionGroup[];
};

const entries = new Map<string, TargetEntry>();
let nextMutationRevision = 0;

export function reactionMutationTargetKey(target: ReactionTarget): string {
    return `${target.kind}:${String(target.id)}`;
}

function entryFor(
    target: ReactionTarget,
    initialReactions: ReactionGroup[],
): TargetEntry {
    const key = reactionMutationTargetKey(target);
    const existing = entries.get(key);
    if (existing) {
        return existing;
    }
    const created: TargetEntry = {
        active: null,
        listeners: new Set(),
        reactions: initialReactions,
    };
    entries.set(key, created);
    return created;
}

function snapshot(entry: TargetEntry): ReactionMutationSnapshot {
    return {
        busy: entry.active !== null,
        reactions: entry.reactions,
    };
}

function notify(
    entry: TargetEntry,
    change?: ReactionChange,
    error?: unknown,
): void {
    const event = {
        change,
        error,
        snapshot: snapshot(entry),
    } satisfies ReactionMutationEvent;
    for (const listener of entry.listeners) {
        listener(event);
    }
}

function removeUnusedEntry(key: string, entry: TargetEntry): void {
    if (
        entry.active === null &&
        entry.listeners.size === 0 &&
        entries.get(key) === entry
    ) {
        entries.delete(key);
    }
}

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

export function subscribeReactionMutation(
    target: ReactionTarget,
    initialReactions: ReactionGroup[],
    listener: Listener,
): () => void {
    const key = reactionMutationTargetKey(target);
    const entry = entryFor(target, initialReactions);
    entry.listeners.add(listener);
    listener({ snapshot: snapshot(entry) });
    return () => {
        entry.listeners.delete(listener);
        removeUnusedEntry(key, entry);
    };
}

export function hydrateReactionMutation(
    target: ReactionTarget,
    reactions: ReactionGroup[],
): void {
    const entry = entryFor(target, reactions);
    if (entry.active !== null || entry.reactions === reactions) {
        return;
    }
    entry.reactions = reactions;
    notify(entry);
}

export function coordinateReactionMutation(
    target: ReactionTarget,
    initialReactions: ReactionGroup[],
    emoji: string,
    csrfToken: string,
):
    | {
          started: false;
      }
    | {
          outcome: Promise<ReactionMutationOutcome>;
          revision: number;
          started: true;
      } {
    const key = reactionMutationTargetKey(target);
    const entry = entryFor(target, initialReactions);
    if (entry.active !== null) {
        return { started: false };
    }

    const previous = entry.reactions;
    const revision = nextMutationRevision + 1;
    nextMutationRevision = revision;
    entry.active = { revision };
    entry.reactions = optimisticGroups(previous, target, emoji);
    notify(entry, {
        reactions: entry.reactions,
        revision,
        source: "optimistic",
    });

    const outcome = toggleReaction(target, emoji, csrfToken)
        .then((authoritative): ReactionMutationOutcome => {
            if (
                entries.get(key) !== entry ||
                entry.active?.revision !== revision
            ) {
                return { status: "stale" };
            }
            entry.active = null;
            entry.reactions = authoritative;
            notify(entry, {
                reactions: authoritative,
                revision,
                source: "authoritative",
            });
            removeUnusedEntry(key, entry);
            return {
                reactions: authoritative,
                revision,
                status: "authoritative",
            };
        })
        .catch((error: unknown): ReactionMutationOutcome => {
            if (
                entries.get(key) !== entry ||
                entry.active?.revision !== revision
            ) {
                return { status: "stale" };
            }
            entry.active = null;
            entry.reactions = previous;
            notify(
                entry,
                {
                    reactions: previous,
                    revision,
                    source: "rollback",
                },
                error,
            );
            removeUnusedEntry(key, entry);
            return {
                error,
                reactions: previous,
                revision,
                status: "rollback",
            };
        });

    return { outcome, revision, started: true };
}

export function resetReactionMutationCoordinatorForTests(): void {
    entries.clear();
    nextMutationRevision = 0;
}
