import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite config
// - "@/..." -> "src/..."
// - Dev proxy:
//   frontend calls /api/*
//   Vite forwards to Flask, so we avoid CORS in dev and keep cookies working.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "https://staging.secretroom.kirillwynn.com",
        changeOrigin: true,
        // IMPORTANT: if backend serves /api as a prefix, we keep it as-is.
        // If later backend routes are not under /api, we can rewrite here.
      },
    },
  },
});