// frontend/src/pages/posts/PostsPage.tsx
// Posts list page (skeleton).
// - Renders a fake list of posts
// - Each post links to the editor route: /app/posts/:id
// - This is purely for verifying routing + guard + layout flow

import { Link } from "react-router-dom";

type FakePost = {
  id: number;
  title: string;
  status: "draft" | "published";
  updated_at: string;
};

const FAKE_POSTS: FakePost[] = [
  { id: 1, title: "First draft", status: "draft", updated_at: "2026-01-07" },
  { id: 2, title: "Second post (published)", status: "published", updated_at: "2026-01-06" },
  { id: 3, title: "Notes / ideas", status: "draft", updated_at: "2026-01-05" },
];

export function PostsPage() {
  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui", maxWidth: 900 }}>
      <header style={{ marginBottom: 12 }}>
        <h1 style={{ fontSize: 20, marginBottom: 6 }}>Posts</h1>
        <p style={{ opacity: 0.75, margin: 0 }}>
          Fake list for now. Next step wires real API + loading/error states.
        </p>
      </header>

      <div
        style={{
          border: "1px solid rgba(0,0,0,0.12)",
          borderRadius: 12,
          overflow: "hidden",
        }}
      >
        {FAKE_POSTS.map((p) => (
          <Link
            key={p.id}
            to={`/app/posts/${p.id}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "12px 14px",
              textDecoration: "none",
              color: "inherit",
              borderBottom: "1px solid rgba(0,0,0,0.08)",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {p.title}
              </div>
              <div style={{ fontSize: 12, opacity: 0.7 }}>
                Updated {p.updated_at}
              </div>
            </div>

            <span
              style={{
                fontSize: 12,
                padding: "4px 8px",
                borderRadius: 999,
                border: "1px solid rgba(0,0,0,0.18)",
                opacity: 0.9,
                flexShrink: 0,
              }}
            >
              {p.status}
            </span>
          </Link>
        ))}
      </div>

      <div
        style={{
          marginTop: 16,
          padding: 16,
          border: "1px solid rgba(0,0,0,0.12)",
          borderRadius: 12,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 6 }}>Coming next</div>
        <ul style={{ margin: 0, paddingLeft: 18, opacity: 0.85 }}>
          <li>GET /api/posts (list)</li>
          <li>POST /api/posts (create draft)</li>
          <li>GET /api/posts/:id (load)</li>
          <li>PUT /api/posts/:id (save)</li>
        </ul>
      </div>
    </div>
  );
}
