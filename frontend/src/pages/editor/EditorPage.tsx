// frontend/src/pages/editor/EditorPage.tsx
// Editor page skeleton.
// - Layout + placeholders only
// - No editor logic yet
// - Will be wired to real editor (TipTap / Toast UI) later

export function EditorPage() {
  return (
    <div
      style={{
        fontFamily: "ui-sans-serif, system-ui",
        maxWidth: 900,
        margin: "0 auto",
      }}
    >
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>Editor</h1>
        <p style={{ opacity: 0.7, margin: 0 }}>
          Draft editor (content, media, metadata).
        </p>
      </header>

      {/* Title */}
      <div style={{ marginBottom: 12 }}>
        <input
          placeholder="Post title"
          disabled
          style={{
            width: "100%",
            fontSize: 18,
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
          }}
        />
      </div>

      {/* Editor placeholder */}
      <div
        style={{
          minHeight: 300,
          padding: 16,
          borderRadius: 12,
          border: "1px solid rgba(0,0,0,0.2)",
          background: "rgba(0,0,0,0.02)",
          marginBottom: 16,
        }}
      >
        <div style={{ opacity: 0.6 }}>
          Editor will live here (TipTap / Markdown).
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 10 }}>
        <button
          disabled
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "white",
            fontWeight: 600,
          }}
        >
          Save draft
        </button>

        <button
          disabled
          style={{
            padding: "8px 12px",
            borderRadius: 10,
            border: "1px solid rgba(0,0,0,0.2)",
            background: "white",
            fontWeight: 600,
          }}
        >
          Publish
        </button>
      </div>
    </div>
  );
}
