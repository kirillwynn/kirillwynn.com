// frontend/src/pages/posts/PostsPage.tsx
// Posts list page (skeleton).
// - Placeholder UI for the admin posts list
// - Next steps will wire real API + loading/error states

export function PostsPage() {
  return (
    <div style={{ fontFamily: "ui-sans-serif, system-ui" }}>
      <h1 style={{ fontSize: 20, marginBottom: 8 }}>Posts</h1>
      <p style={{ opacity: 0.75, marginTop: 0 }}>
        This will become the posts list (drafts + published) with actions.
      </p>

      <div
        style={{
          marginTop: 16,
          padding: 16,
          border: "1px solid rgba(0,0,0,0.12)",
          borderRadius: 12,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Coming next</div>
        <ul style={{ margin: 0, paddingLeft: 18, opacity: 0.85 }}>
          <li>GET /api/posts (list)</li>
          <li>POST /api/posts (create draft)</li>
          <li>Links to editor: /app/posts/:id</li>
        </ul>
      </div>
    </div>
  );
}
