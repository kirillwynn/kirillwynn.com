// frontend/src/pages/editor/editorUtils.ts

export function formatIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function normalizeTitle(raw: string): string {
  return raw.trim();
}

// Stable stringify so we can compare JSON snapshots reliably.
// (Avoids PATCH spam due to key order differences)
export function stableStringify(value: unknown): string {
  const seen = new WeakSet<object>();

  function normalize(v: any): any {
    if (v === null || typeof v !== "object") return v;
    if (seen.has(v)) return null;
    seen.add(v);
    if (Array.isArray(v)) return v.map(normalize);
    const out: Record<string, any> = {};
    for (const k of Object.keys(v).sort()) out[k] = normalize(v[k]);
    return out;
  }

  return JSON.stringify(normalize(value));
}

export function isEnter(e: React.KeyboardEvent<HTMLInputElement>) {
  return e.key === "Enter";
}
