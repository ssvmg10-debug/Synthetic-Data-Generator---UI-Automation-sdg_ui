import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Vite config for local dev; backend runs on http://localhost:8001 (or BACKEND_PORT)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/synthetic": "http://localhost:8001",
      "/ui": "http://localhost:8001",
      "/api": "http://localhost:8001",
      "/chats": "http://localhost:8001"
    }
  },
  build: {
    outDir: "dist"
  }
});

