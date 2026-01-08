// frontend/src/pages/editor/usePostAutosave.ts
//
// Holds autosave logic:
// - draft states (title + bodyJsonStr)
// - lastServer snapshot refs (avoid PATCH spam)
// - buildPatch + debounce + flushSaveNow
// - hydrateFromServer(post) to sync editor + drafts

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

  // Debounce timer
  const saveTimerRef = useRef<number | null>(null);

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

  const scheduleDebouncedSave = useCallback(() => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      void flushSaveNow("debounce");
    }, 600);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId, enabled, buildPatch, titleDraft, bodyJsonStrDraft, editor]);

  const flushSaveNow = useCallback(
    async (reason: FlushReason = "manual") => {
      if (!postId) return;
      if (!enabled) return;

      const normalizedTitle = normalizeTitle(titleDraft);

      // Only enforce “title required” on explicit user actions.
      // Clicking toolbar should not suddenly error just because title is temporarily empty.
      if ((reason === "blur" || reason === "manual") && normalizedTitle.length === 0) {
        setSaveState({ kind: "error", message: "Title cannot be empty." });
        return;
      }

      const patch = buildPatch();
      if (!patch) return;

      setSaveState({ kind: "saving" });

      try {
        const res = await patchPost(postId, patch as any);

        if (!res.ok) {
          setSaveState({ kind: "error", message: res.error || "Failed to save." });
          return;
        }

        if (res.item) {
          // Update snapshots/drafts from server response
          const newTitle = res.item.title ?? lastServerTitleRef.current;
          lastServerTitleRef.current = newTitle ?? "";
          setTitleDraft(newTitle ?? "");

          const newBodyJsonFromApi = (res.item as any).body_json as JSONContent | null | undefined;

          if (editor) {
            if (newBodyJsonFromApi && typeof newBodyJsonFromApi === "object") {
              editor.commands.setContent(newBodyJsonFromApi, { emitUpdate: false });
            }
            const jsonStr = stableStringify(editor.getJSON());
            setBodyJsonStrDraft(jsonStr);
            lastServerBodyJsonStrRef.current = jsonStr;
          } else {
            // If editor is not ready, still advance snapshot
            lastServerBodyJsonStrRef.current = bodyJsonStrDraft;
          }

          onPostUpdated?.(res.item);
        } else {
          // Fallback: assume patch succeeded
          if (patch.title !== undefined) lastServerTitleRef.current = String(patch.title ?? "");
          if (editor) {
            const jsonStr = stableStringify(editor.getJSON());
            lastServerBodyJsonStrRef.current = jsonStr;
            setBodyJsonStrDraft(jsonStr);
          }
        }

        setSaveState({ kind: "saved", at: Date.now() });
      } catch (e: any) {
        setSaveState({
          kind: "error",
          message: e?.message || "Unexpected error while saving.",
        });
      }
    },
    [postId, enabled, titleDraft, buildPatch, editor, bodyJsonStrDraft, onPostUpdated],
  );

  // Debounced autosave on real changes
  useEffect(() => {
    if (!enabled) return;
    if (!buildPatch()) return;

    scheduleDebouncedSave();

    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [enabled, titleDraft, bodyJsonStrDraft, buildPatch, scheduleDebouncedSave]);

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
          // Fallback: if we have legacy html in body_md
          editor.commands.setContent(bodyHtmlLegacy || "", { emitUpdate: false });
        }

        const hydratedJsonStr = stableStringify(editor.getJSON());
        setBodyJsonStrDraft(hydratedJsonStr);
        lastServerBodyJsonStrRef.current = hydratedJsonStr;
      } else {
        setBodyJsonStrDraft("");
        lastServerBodyJsonStrRef.current = "";
      }

      setSaveState({ kind: "idle" });
    },
    [editor],
  );

  return useMemo(
    () => ({
      titleDraft,
      setTitleDraft,
      bodyJsonStrDraft,
      setBodyJsonStrDraft,
      saveState,
      flushSaveNow,
      hydrateFromServer,
    }),
    [titleDraft, bodyJsonStrDraft, saveState, flushSaveNow, hydrateFromServer],
  );
}
