// frontend/src/pages/editor/usePostAutosave.ts
//
// Holds autosave logic:
// - draft states (title + bodyJsonStr)
// - lastServer snapshot refs (avoid PATCH spam)
// - debounce + max-wait + manual flush
// - "Google Docs style" safety flush on:
//   - Cmd/Ctrl+S
//   - visibilitychange (tab hidden)
//   - pagehide (navigate away / close tab)
//
// IMPORTANT:
// Never call `editor.commands.setContent()` as part of autosave responses.
// Doing so can override the user's in-flight edits (e.g. during delete) and "bring back" characters.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Editor, JSONContent } from "@tiptap/react";

import { patchPost, type PostItem } from "@/api/posts";
import { normalizeTitle, stableStringify } from "./editorUtils";

export type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; at: number }
  | { kind: "error"; message: string };

type FlushReason = "debounce" | "blur" | "manual";

const SAVE_DEBOUNCE_MS = 5000;
const SAVE_MAX_WAIT_MS = 30000;

type FlushOpts = {
  keepalive?: boolean;
};

export function usePostAutosave(args: {
  postId: number | null;
  editor: Editor | null;
  enabled: boolean; // state.kind === "ready"
  onPostUpdated?: (post: PostItem) => void;
}) {
  const { postId, editor, enabled, onPostUpdated } = args;

  // Drafts
  const [titleDraft, setTitleDraft] = useState("");
  const [bodyJsonStrDraft, setBodyJsonStrDraft] = useState<string>("");

  // Save status
  const [saveState, setSaveState] = useState<SaveState>({ kind: "idle" });

  // Keep last server snapshot to avoid PATCH spam
  const lastServerTitleRef = useRef<string>("");
  const lastServerBodyJsonStrRef = useRef<string>("");

  // Debounce + max-wait timers
  const saveTimerRef = useRef<number | null>(null);
  const maxWaitTimerRef = useRef<number | null>(null);

  // Prevent concurrent saves; queue a follow-up save if changes happen during an in-flight request.
  const inFlightRef = useRef(false);
  const pendingRef = useRef(false);

  const clearDebounceTimer = useCallback(() => {
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }, []);

  const clearMaxWaitTimer = useCallback(() => {
    if (maxWaitTimerRef.current) {
      window.clearTimeout(maxWaitTimerRef.current);
      maxWaitTimerRef.current = null;
    }
  }, []);

  const buildPatch = useCallback((): Record<string, unknown> | null => {
    const patch: Record<string, unknown> = {};

    const nextTitle = normalizeTitle(titleDraft);
    const serverTitle = normalizeTitle(lastServerTitleRef.current);
    if (nextTitle !== serverTitle) {
      // Don’t autosave invalid title
      if (nextTitle.length > 0) patch.title = nextTitle;
    }

    if (bodyJsonStrDraft !== lastServerBodyJsonStrRef.current) {
      patch.body_json = editor ? editor.getJSON() : null;
    }

    return Object.keys(patch).length ? patch : null;
  }, [titleDraft, bodyJsonStrDraft, editor]);

  const flushSaveNow = useCallback(
    async (reason: FlushReason = "manual", opts: FlushOpts = {}) => {
      if (!postId) return;
      if (!enabled) return;

      // If a save is already in-flight, request a follow-up save.
      if (inFlightRef.current) {
        pendingRef.current = true;
        return;
      }

      // Cancel any scheduled saves when doing an explicit flush attempt.
      clearDebounceTimer();
      clearMaxWaitTimer();

      const normalizedTitle = normalizeTitle(titleDraft);

      // Only enforce “title required” on explicit user actions.
      if ((reason === "blur" || reason === "manual") && normalizedTitle.length === 0) {
        setSaveState({ kind: "error", message: "Title cannot be empty." });
        return;
      }

      const patch = buildPatch();
      if (!patch) return;

      // Capture exactly what we are sending, so we can update server snapshots safely
      // even if the user continues typing while the request is in flight.
      const sentTitle = patch.title !== undefined ? String(patch.title ?? "") : null;
      const sentBodyJsonStr = patch.body_json !== undefined ? bodyJsonStrDraft : null;

      inFlightRef.current = true;
      setSaveState({ kind: "saving" });

      try {
        const res = await patchPost(postId, patch as any, { keepalive: !!opts.keepalive });

        if (!res.ok) {
          setSaveState({ kind: "error", message: res.error || "Failed to save." });
          return;
        }

        // Update "last server snapshot" WITHOUT mutating the editor content.
        if (res.item) {
          // Title snapshot: prefer server response (it might normalize), fallback to what we sent.
          if (typeof res.item.title === "string") {
            lastServerTitleRef.current = res.item.title;
          } else if (sentTitle !== null) {
            lastServerTitleRef.current = sentTitle;
          }

          // Body snapshot: trust what we sent (avoid applying server echo to editor).
          if (sentBodyJsonStr !== null) {
            lastServerBodyJsonStrRef.current = sentBodyJsonStr;
          }

          onPostUpdated?.(res.item);
        } else {
          // Fallback: assume patch succeeded
          if (sentTitle !== null) lastServerTitleRef.current = sentTitle;
          if (sentBodyJsonStr !== null) lastServerBodyJsonStrRef.current = sentBodyJsonStr;
        }

        setSaveState({ kind: "saved", at: Date.now() });
      } catch (e: any) {
        setSaveState({
          kind: "error",
          message: e?.message || "Unexpected error while saving.",
        });
      } finally {
        inFlightRef.current = false;

        // If edits happened while we were saving, try again immediately.
        if (pendingRef.current) {
          pendingRef.current = false;
          window.setTimeout(() => {
            void flushSaveNow("debounce");
          }, 0);
        }
      }
    },
    [
      postId,
      enabled,
      titleDraft,
      buildPatch,
      bodyJsonStrDraft,
      onPostUpdated,
      clearDebounceTimer,
      clearMaxWaitTimer,
    ],
  );

  const scheduleDebouncedSave = useCallback(() => {
    clearDebounceTimer();
    saveTimerRef.current = window.setTimeout(() => {
      void flushSaveNow("debounce");
    }, SAVE_DEBOUNCE_MS);
  }, [flushSaveNow, clearDebounceTimer]);

  const ensureMaxWaitSave = useCallback(() => {
    // Start max-wait only once per "dirty session".
    if (maxWaitTimerRef.current) return;
    maxWaitTimerRef.current = window.setTimeout(() => {
      void flushSaveNow("debounce");
    }, SAVE_MAX_WAIT_MS);
  }, [flushSaveNow]);

  // Autosave scheduling:
  // - Debounce: save after user pauses.
  // - Max-wait: even if user never pauses, save at least once per window.
  useEffect(() => {
    if (!enabled) {
      clearDebounceTimer();
      clearMaxWaitTimer();
      return;
    }

    const patch = buildPatch();
    if (!patch) {
      clearDebounceTimer();
      clearMaxWaitTimer();
      return;
    }

    scheduleDebouncedSave();
    ensureMaxWaitSave();
  }, [
    enabled,
    titleDraft,
    bodyJsonStrDraft,
    buildPatch,
    scheduleDebouncedSave,
    ensureMaxWaitSave,
    clearDebounceTimer,
    clearMaxWaitTimer,
  ]);

  // Google-Docs style "safety flush":
  // - Cmd/Ctrl+S
  // - tab hidden
  // - pagehide (navigate away / close tab)
  useEffect(() => {
    if (!enabled) return;
    if (!postId) return;

    function onKeyDown(e: KeyboardEvent) {
      const key = e.key.toLowerCase();
      if (key !== "s") return;

      const isMod = e.metaKey || e.ctrlKey;
      if (!isMod) return;

      e.preventDefault();
      void flushSaveNow("manual");
    }

    function onVisibilityChange() {
      if (document.visibilityState !== "hidden") return;
      void flushSaveNow("manual");
    }

    function onPageHide() {
      // Best effort: allow request to continue during unload.
      void flushSaveNow("manual", { keepalive: true });
    }

    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", onPageHide);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [enabled, postId, flushSaveNow]);

  // Clear timers on unmount
  useEffect(() => {
    return () => {
      clearDebounceTimer();
      clearMaxWaitTimer();
    };
  }, [clearDebounceTimer, clearMaxWaitTimer]);

  const hydrateFromServer = useCallback(
    (post: PostItem) => {
      const title = post.title ?? "";
      setTitleDraft(title);
      lastServerTitleRef.current = title;

      const bodyJsonFromApi = (post as any).body_json as JSONContent | null | undefined;
      const bodyHtmlLegacy = (post as any).body_md as string | null | undefined;

      if (editor) {
        if (bodyJsonFromApi && typeof bodyJsonFromApi === "object") {
          editor.commands.setContent(bodyJsonFromApi, { emitUpdate: false });
        } else {
          // Fallback: legacy HTML/markdown string (best-effort)
          editor.commands.setContent(bodyHtmlLegacy || "", { emitUpdate: false });
        }

        const hydratedJsonStr = stableStringify(editor.getJSON());
        setBodyJsonStrDraft(hydratedJsonStr);
        lastServerBodyJsonStrRef.current = hydratedJsonStr;
      } else {
        setBodyJsonStrDraft("");
        lastServerBodyJsonStrRef.current = "";
      }

      pendingRef.current = false;
      inFlightRef.current = false;

      clearDebounceTimer();
      clearMaxWaitTimer();

      setSaveState({ kind: "idle" });
    },
    [editor, clearDebounceTimer, clearMaxWaitTimer],
  );

  return useMemo(
    () => ({
      titleDraft,
      setTitleDraft,
      bodyJsonStrDraft,
      setBodyJsonStrDraft,
      saveState,
      flushSaveNow: (reason?: FlushReason) => flushSaveNow(reason ?? "manual"),
      hydrateFromServer,
    }),
    [titleDraft, bodyJsonStrDraft, saveState, flushSaveNow, hydrateFromServer],
  );
}
