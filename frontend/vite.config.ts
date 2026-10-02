import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    sourcemap: true,
    target: "es2022",
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/mcp": "http://localhost:8000",
    },
  },
});
