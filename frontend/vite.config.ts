import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api and /ws to the FastAPI backend during local development so the
// dashboard can just call relative paths instead of hard-coding a host.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
});
