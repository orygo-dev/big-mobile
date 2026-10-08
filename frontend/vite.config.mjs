import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    resolve: {alias: {"@": path.resolve(import.meta.dirname, "src")}},
    define: {"process.env.REACT_APP_BACKEND_URL": JSON.stringify(mode === "test" ? "" : env.REACT_APP_BACKEND_URL || "")},
    build: {outDir: "build", sourcemap: false},
    server: {strictPort: true, proxy: {"/api": "http://127.0.0.1:8000"}},
    test: {globals: true, environment: "jsdom", setupFiles: ["./src/test-setup.js"], maxWorkers: 1, pool: "threads", isolate: false},
  };
});
