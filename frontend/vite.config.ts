import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Vite config for local dev; backend runs on BACKEND_PORT (default 8000) or 8001
const backendPort = process.env.BACKEND_PORT || process.env.VITE_BACKEND_PORT || "8000";
const backendUrl = `http://localhost:${backendPort}`;
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/synthetic": backendUrl,
      "/ui": backendUrl,
      "/api": backendUrl,
      "/chats": backendUrl
    }
  },
  build: {
    outDir: "dist"
  }
});

