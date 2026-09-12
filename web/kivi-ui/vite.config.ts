import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    setupFiles: ["./src/test-setup.ts"],
  },
  base: "/static/dist/",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/chat": "http://localhost:8002",
      "/health": "http://localhost:8002",
      "/lexical": "http://localhost:8002",
      "/memories": "http://localhost:8002",
      "/dictations": "http://localhost:8002",
      "/stats": "http://localhost:8002",
    },
  },
});
