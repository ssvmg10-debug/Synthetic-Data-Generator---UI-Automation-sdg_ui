import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// Vite config for local dev; backend runs on http://localhost:8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/synthetic": "http://localhost:8000",
      "/ui": "http://localhost:8000",
      "/api": "http://localhost:8000"
    }
  },
  build: {
    outDir: "dist"
  }
});

