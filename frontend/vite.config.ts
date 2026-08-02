import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    // Match docker-compose's FRONTEND_HOST_PORT mapping and stay reachable
    // from outside the container — Vite defaults to localhost-only binding.
    host: true,
    port: 3000,
    // Docker Desktop on Windows doesn't reliably forward inotify events for
    // bind-mounted host directories, so native file-watching silently misses
    // edits (JS/TSX transform cache goes stale even though CSS, which Vite
    // re-reads per-request, keeps working) — poll instead.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
