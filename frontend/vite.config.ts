import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite config
// - Adds an import alias: "@/..." -> "src/..."
// - Keeps config minimal; we'll add proxy/CSP later when wiring to backend API.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
