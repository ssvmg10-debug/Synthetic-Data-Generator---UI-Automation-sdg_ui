import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Vite config for local dev; backend port from env (start_backend writes to .env + frontend/.env)
const backendPort = process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || "8001";
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

