// frontend/src/pages/posts/PostsPage.tsx
// Posts list page (minimal working v1).
// - Loads posts via GET /api/posts
// - Creates a draft via POST /api/posts
// - Navigates to /app/posts/:id after create

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, type ApiPostListItem } from "@/lib/api";

export function PostsPage() {
  const nav = useNavigate();

  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string>("");
  const [items, setItems] = useState<ApiPostListItem[]>([]);

  async function load() {
    setError("");
    setLoading(true);
    try {
      const res = await api.postsList();
      if (!res.ok) throw new Error(res.error);
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load posts");
    } finally {
      setLoading(false);
    }
  }

  async function onNewDraft() {
    setError("");
    setCreating(true);
    try {
      const res = await api.postsCreateDraft();
      if (!res.ok) throw new Error(res.error);
      nav(`/app/posts/${res.post.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create post");
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, marginBottom: 6 }}>Posts</h1>
          <p style={{ opacity: 0.75, marginTop: 0 }}>
            Drafts + published posts.
          </p>
        </div>

        <button
          type="button"
          onClick={onNewDraft}
          disabled={creating || loading}
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "white",
            cursor: creating || loading ? "default" : "pointer",
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          {creating ? "Creating..." : "New draft"}
        </button>
      </div>

      {error ? (
        <div
          role="alert"
          style={{
            marginTop: 12,
            padding: 10,
            borderRadius: 10,
            background: "rgba(255,0,0,0.08)",
            border: "1px solid rgba(255,0,0,0.25)",
          }}
        >
          {error}
        </div>
      ) : null}

      <div
        style={{
          marginTop: 16,
          padding: 16,
          border: "1px solid rgba(0,0,0,0.12)",
          borderRadius: 12,
        }}
      >
        {loading ? (
          <div style={{ opacity: 0.75 }}>Loading...</div>
        ) : items.length === 0 ? (
          <div style={{ opacity: 0.75 }}>No posts yet.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {items.map((p) => (
              <li key={p.id} style={{ marginBottom: 6 }}>
                <a
                  href={`/app/posts/${p.id}`}
                  style={{ textDecoration: "none", fontWeight: 600 }}
                >
                  {p.title || "Untitled"}
                </a>
                <span style={{ opacity: 0.7 }}> — {p.status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div style={{ marginTop: 10, opacity: 0.6, fontSize: 12 }}>
        API: GET /api/posts, POST /api/posts
      </div>
    </div>
  );
}
